from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Dict, Optional


from yt_allinone.src.core.models import DownloadError, ErrorCode


class FFmpegError(RuntimeError):
    def to_download_error(self) -> DownloadError:
        msg = str(self)
        lower = msg.lower()
        if "not found in path" in lower:
            return DownloadError(code=ErrorCode.FFMPEG_MISSING, message=msg, hint="Cài ffmpeg/ffprobe và thêm vào PATH.")
        if "no space" in lower or "no space left" in lower or "disk full" in lower:
            return DownloadError(code=ErrorCode.NO_SPACE, message=msg, hint="Giải phóng dung lượng ổ đĩa.")
        return DownloadError(code=ErrorCode.UNKNOWN, message=msg, hint="Kiểm tra cài đặt ffmpeg và đầu vào.")


def _run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.strip() or "ffmpeg/ffprobe failed")
    return proc


def _ensure_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise FFmpegError(f"{name} not found in PATH")


def extract_mp3(
    video_path: str,
    mp3_path: str,
    meta: Dict[str, str],
    cover_path: Optional[str] = None,
) -> None:
    """Extract best audio from input and convert to MP3 with metadata and optional cover.

    - Uses libmp3lame with quality q:a 0 (V0)
    - Adds ID3v2.3 tags title/artist if provided in meta
    - If cover_path provided, embeds as front cover
    - Verifies output via ffprobe
    """
    try:
        _ensure_tool("ffmpeg")
        _ensure_tool("ffprobe")
    except FFmpegError as e:
        raise e.to_download_error()

    if not os.path.exists(video_path):
        raise FFmpegError(f"Input not found: {video_path}")
    os.makedirs(os.path.dirname(os.path.abspath(mp3_path)) or ".", exist_ok=True)

    base_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
    ]

    if cover_path:
        if not os.path.exists(cover_path):
            raise FFmpegError(f"Cover not found: {cover_path}")
        base_cmd += ["-i", cover_path, "-map", "0:a", "-map", "1:v", "-id3v2_version", "3"]
        # set cover stream metadata
        base_cmd += [
            "-metadata:s:v",
            "title=Album cover",
            "-metadata:s:v",
            "comment=Cover (front)",
        ]
    else:
        base_cmd += ["-vn"]

    # global tags
    if title := meta.get("title"):
        base_cmd += ["-metadata", f"title={title}"]
    if artist := meta.get("artist"):
        base_cmd += ["-metadata", f"artist={artist}"]

    base_cmd += ["-acodec", "libmp3lame", "-q:a", "0", mp3_path]

    try:
        _run_cmd(base_cmd)
    except FFmpegError as e:
        raise e.to_download_error()

    # Verify
    try:
        probe = _run_cmd([
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        mp3_path,
    ])
    except FFmpegError as e:
        raise e.to_download_error()
    data = json.loads(probe.stdout or "{}")
    streams = data.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" and s.get("codec_name") == "mp3" for s in streams)
    if not has_audio:
        raise DownloadError(code=ErrorCode.UNKNOWN, message="Output MP3 verification failed: no mp3 audio stream", hint=None)
    if cover_path:
        has_cover = any(s.get("codec_type") == "video" for s in streams)
        if not has_cover:
            raise DownloadError(code=ErrorCode.UNKNOWN, message="Cover embedding verification failed", hint=None)

