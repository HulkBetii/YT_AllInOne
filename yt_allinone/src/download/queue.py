from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Optional, TypeVar

import psutil
from collections import deque
from yt_dlp import YoutubeDL

from yt_allinone.src.core.models import DownloadTask
from yt_allinone.src.core.selector import build_format_selector


T = TypeVar("T")


class SimpleQueue:
    def __init__(self) -> None:
        self._q: Deque[T] = deque()

    def put(self, item: T) -> None:
        self._q.append(item)

    def get(self) -> Optional[T]:
        return self._q.popleft() if self._q else None

    def empty(self) -> bool:
        return not self._q


# ---------------- Worker (subprocess entry) ----------------

def _progress_hook_factory() -> Callable[[Dict[str, Any]], None]:
    def hook(status: Dict[str, Any]) -> None:
        payload = {
            "event": "progress",
            "status": status.get("status"),
            "downloaded_bytes": status.get("downloaded_bytes"),
            "total_bytes": status.get("total_bytes") or status.get("total_bytes_estimate"),
            "speed": status.get("speed"),
            "eta": status.get("eta"),
            "filename": status.get("filename"),
            "frag_index": status.get("fragment_index"),
            "frag_count": status.get("fragment_count"),
        }
        sys.stdout.write(json.dumps(payload) + "\n")
        sys.stdout.flush()

    return hook


def _run_worker(config_path: str) -> int:
    with open(config_path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    url = cfg["url"]
    opts = cfg["ydl_opts"]
    opts = dict(opts)
    hooks = opts.get("progress_hooks") or []
    hooks.append(_progress_hook_factory())
    opts["progress_hooks"] = hooks

    # Ensure resume semantics
    opts.setdefault("continuedl", True)
    opts.setdefault("overwrites", False)
    opts.setdefault("retries", 10)
    opts.setdefault("fragment_retries", 10)
    opts.setdefault("retry_sleep_functions", {
        "http": {"times": 10, "backoff": "exp", "interval": 1, "max": 10},
    })

    try:
        with YoutubeDL(params=opts) as ydl:
            ydl.extract_info(url, download=True)
        sys.stdout.write(json.dumps({"event": "done"}) + "\n")
        sys.stdout.flush()
        return 0
    except Exception as exc:  # pragma: no cover (error path)
        sys.stdout.write(json.dumps({"event": "error", "message": str(exc)}) + "\n")
        sys.stdout.flush()
        return 1


# ---------------- Download Manager ----------------

ProgressCallback = Callable[[Dict[str, Any]], None]


class DownloadManager:
    def __init__(self) -> None:
        self._current: Optional[DownloadTask] = None
        self._proc: Optional[subprocess.Popen] = None
        self._ps: Optional[psutil.Process] = None
        self._progress_callbacks: List[ProgressCallback] = []
        self._reader_thread: Optional[threading.Thread] = None
        self._config_file: Optional[str] = None

    def on_progress(self, cb: ProgressCallback) -> None:
        self._progress_callbacks.append(cb)

    def _emit(self, data: Dict[str, Any]) -> None:
        for cb in list(self._progress_callbacks):
            try:
                cb(data)
            except Exception:
                pass

    def _build_ydl_opts(self, task: DownloadTask) -> Dict[str, Any]:
        outtmpl = os.path.join(task.outdir, "%(title)s.%(ext)s")
        fmt = "bestaudio/best" if task.only_audio else build_format_selector(task.quality)
        ydl_opts: Dict[str, Any] = {
            "format": fmt,
            "outtmpl": outtmpl,
            "continuedl": True,
            "overwrites": False,
            "noplaylist": False,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [],
        }
        if task.only_audio:
            ydl_opts["postprocessors"].append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })
        ydl_opts.update(task.options or {})
        return ydl_opts

    def _write_config(self, task: DownloadTask) -> str:
        ydl_opts = self._build_ydl_opts(task)
        os.makedirs(task.outdir, exist_ok=True)
        payload = {"url": task.url, "ydl_opts": ydl_opts}
        fd, path = tempfile.mkstemp(prefix="ytai_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return path

    def start(self, task: DownloadTask) -> None:
        if self._proc and self._proc.poll() is None:
            raise RuntimeError("A task is already running")
        self._current = task
        self._config_file = self._write_config(task)

        # Launch subprocess running this module as a worker
        cmd = [
            sys.executable,
            "-u",
            "-m",
            "yt_allinone.src.download.queue",
            "--worker",
            self._config_file,
        ]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self._ps = psutil.Process(self._proc.pid)

        # Reader thread to dispatch progress
        assert self._proc.stdout is not None
        def _reader() -> None:
            for line in self._proc.stdout:
                try:
                    data = json.loads(line.strip())
                except Exception:
                    continue
                self._emit(data)

        self._reader_thread = threading.Thread(target=_reader, daemon=True)
        self._reader_thread.start()

    def pause(self) -> None:
        if not self._ps:
            return
        try:
            self._ps.suspend()
            self._emit({"event": "paused"})
        except Exception:
            pass

    def resume(self) -> None:
        if not self._ps:
            return
        try:
            self._ps.resume()
            self._emit({"event": "resumed"})
        except Exception:
            pass

    def cancel(self, delete_part: bool = False) -> None:
        if not self._proc:
            return
        try:
            self._emit({"event": "cancelling"})
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        finally:
            if delete_part and self._current:
                # Best-effort: remove leftover .part files in outdir
                outdir = self._current.outdir
                for name in os.listdir(outdir):
                    if name.endswith(".part"):
                        try:
                            os.remove(os.path.join(outdir, name))
                        except Exception:
                            pass
            self._proc = None
            self._ps = None


if __name__ == "__main__":  # Subprocess entry point
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        sys.exit(_run_worker(sys.argv[2]))

