from __future__ import annotations

import os
import shutil
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, BarColumn, TimeRemainingColumn, DownloadColumn, TransferSpeedColumn

from .core.selector import build_format_selector
from .core.filters import is_shorts, is_regular
from .core.exporter import download_best_thumbnail, export_tags
from .utils.text_utils import make_safe_filename
from .core.models import DownloadTask
from .download.ytdlp_wrapper import YtDlpWrapper
from .utils.config import get_default_download_dir
from .download.queue import DownloadManager


app = typer.Typer(add_completion=False, help="""
YouTube All-in-one tool.

Examples:
  yttool get https://youtu.be/dQw4w9WgXcQ --quality 1080p --out downloads
  yttool get https://youtube.com/playlist?list=PL... --only-shorts --dry-run
  yttool get https://youtube.com/@handle --only-regular --limit 10 --export-tags --thumb
""")
console = Console()


def _choose_filter(only_shorts: bool, only_regular: bool):
    if only_shorts and only_regular:
        raise typer.BadParameter("Cannot use both --only-shorts and --only-regular")
    if only_shorts:
        return is_shorts
    if only_regular:
        return is_regular
    return None


@app.command(help="""
Fetch entries from one or many inputs and optionally download.

If --dry-run is set, only list entries with a table. Otherwise, download entries sequentially.
You can pass multiple URLs separated by space.
""")
def get(
    urls: List[str] = typer.Argument(..., help="One or many Video/playlist/channel/handle URLs", metavar="URL ..."),
    quality: str = typer.Option("best", "--quality", help="best|1080p|720p|480p"),
    only_audio: bool = typer.Option(False, "--only-audio", help="Extract audio only"),
    only_shorts: bool = typer.Option(False, "--only-shorts", help="Filter Shorts only"),
    only_regular: bool = typer.Option(False, "--only-regular", help="Filter non-Shorts"),
    limit: Optional[int] = typer.Option(None, "--limit", min=1, help="Max number of items"),
    thumb: bool = typer.Option(False, "--thumb", help="Download best thumbnail"),
    subtitles_only: bool = typer.Option(False, "--subs-only", help="Download subtitles only and skip media"),
    safe_mode: bool = typer.Option(False, "--safe-mode", help="Increase request sleep/retries to reduce 429 and flakiness"),
    user_agent: Optional[str] = typer.Option(None, "--user-agent", help="Custom User-Agent header to mimic your browser"),
    export_tags_flag: bool = typer.Option(False, "--export-tags", help="Export tags.csv and tags.json"),
    outdir: str = typer.Option(get_default_download_dir(), "--out", help="Output directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not download, only list"),
    cookies_from_browser: Optional[str] = typer.Option(None, "--cookies-from-browser", help="chrome|edge|firefox"),
) -> None:
    filter_fn = _choose_filter(only_shorts, only_regular)

    # Build yt-dlp wrapper options
    ydl_opts = {
        "geo_bypass": True,
    }
    if safe_mode:
        ydl_opts.update({
            "retries": 10,
            "fragment_retries": 10,
            "retry_sleep_functions": {"http": {"times": 10, "backoff": "exp", "interval": 1, "max": 10}},
            "sleep_requests": 2,
            "file_access_retries": 10,
        })
    if user_agent:
        ydl_opts["http_headers"] = {"User-Agent": user_agent}
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)

    wrapper = YtDlpWrapper(options=ydl_opts)

    if dry_run:
        all_entries = []
        for u in urls:
            entries = wrapper.dry_run(u, filter_fn=filter_fn, limit=limit)
            all_entries.extend(entries)
        table = Table(title="Dry Run Entries")
        table.add_column("#", justify="right")
        table.add_column("id")
        table.add_column("title")
        table.add_column("duration")
        table.add_column("url")
        for idx, e in enumerate(all_entries, 1):
            table.add_row(str(idx), e.id, e.title or "", str(e.duration or ""), e.url or "")
        console.print(table)

        if thumb:
            os.makedirs(outdir, exist_ok=True)
            for e in all_entries:
                path = download_best_thumbnail(e.id, e.raw.get("thumbnails") if e.raw else None)
                if path:
                    safe_title = make_safe_filename(e.title or e.id)
                    dest = os.path.join(outdir, f"thumbnail_{safe_title}.jpg")
                    try:
                        shutil.move(path, dest)
                        console.print(f"Saved thumbnail: {dest}")
                    except Exception:
                        console.print(f"Saved thumbnail temp: {path}")

        if export_tags_flag:
            export_tags((e.raw or {"id": e.id, "title": e.title, "tags": e.raw.get("tags") if e.raw else []} for e in all_entries), outdir)
        return

    # Actual download
    os.makedirs(outdir, exist_ok=True)
    # Aggregate entries from all inputs
    entries = []
    for u in urls:
        entries.extend(wrapper.dry_run(u, filter_fn=filter_fn, limit=limit))

    manager = DownloadManager()
    progress = Progress(
        "{task.description}",
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    )

    def on_prog(ev):  # type: ignore[no-untyped-def]
        event = ev.get("event")
        if event == "error":
            console.print(f"[red]Download failed: {ev.get('message')}[/red]")
            return
        if event == "done":
            console.print("[green]Download finished[/green]")
            return
        if event != "progress":
            return
        status = ev.get("status")
        downloaded = ev.get("downloaded_bytes") or 0
        total = ev.get("total_bytes") or 0
        # Show a simple textual progress line
        if total:
            pct = downloaded / total * 100
            console.print(f"[{status}] {downloaded}/{total} bytes ({pct:.1f}%) speed={ev.get('speed') or ''} eta={ev.get('eta') or ''}", highlight=False)
        else:
            console.print(f"[{status}] {downloaded} bytes", highlight=False)

    manager.on_progress(on_prog)

    for e in entries:
        dl_options = {}
        if subtitles_only:
            dl_options.update({
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                # prefer Vietnamese/English then best
                "subtitleslangs": ["vi", "vi.*", "en", "en.*", "best"],
                # Prefer srt first, fallback once to best
                "subtitlesformat": "srt/best",
                "sleep_requests": 2,
            })
        else:
            fmt = build_format_selector(quality)
            dl_options["format"] = fmt
        if cookies_from_browser:
            dl_options["cookiesfrombrowser"] = (cookies_from_browser,)
        if safe_mode:
            dl_options.update({
                "retries": 10,
                "fragment_retries": 10,
                "retry_sleep_functions": {"http": {"times": 10, "backoff": "exp", "interval": 1, "max": 10}},
                "file_access_retries": 10,
            })
        if user_agent:
            dl_options["http_headers"] = {"User-Agent": user_agent}
        task = DownloadTask(
            url=e.url or e.webpage_url or f"https://www.youtube.com/watch?v={e.id}",
            outdir=outdir,
            quality=quality,
            only_audio=only_audio if not subtitles_only else False,
            options=dl_options,
        )
        console.print("Downloading subtitles: " + (task.url if subtitles_only else f"{task.url}"))
        manager.start(task)
        # Wait for completion
        # In this simple version, we join by waiting on the reader thread to finish when process exits
        if manager._proc:  # noqa: SLF001 (access internal for simplicity)
            manager._proc.wait()

    # Download thumbnails when not in dry-run mode
    if thumb:
        for e in entries:
            try:
                path = download_best_thumbnail(e.id, e.raw.get("thumbnails") if e.raw else None)
                if path:
                    safe_title = make_safe_filename(e.title or e.id)
                    dest = os.path.join(outdir, f"thumbnail_{safe_title}.jpg")
                    try:
                        shutil.move(path, dest)
                        console.print(f"Saved thumbnail: {dest}")
                    except Exception:
                        console.print(f"Saved thumbnail temp: {path}")
            except Exception as ex:  # pragma: no cover
                console.print(f"[red]Failed to save thumbnail for {e.id}: {ex}[/red]")

    if export_tags_flag:
        export_tags((e.raw or {"id": e.id, "title": e.title, "tags": e.raw.get("tags") if e.raw else []} for e in entries), outdir)


@app.command()
def pause(task_id: str) -> None:
    """Pause a running task (not persisted between runs)."""
    console.print("Pause is supported only for current session manager in this prototype.")


@app.command()
def resume(task_id: str) -> None:
    """Resume a paused task (not persisted between runs)."""
    console.print("Resume is supported only for current session manager in this prototype.")


@app.command()
def cancel(task_id: str) -> None:
    """Cancel a running task (not persisted between runs)."""
    console.print("Cancel is supported only for current session manager in this prototype.")


@app.command()
def version() -> None:
    """Show version."""
    console.print("yt-allinone v0.1.0")


@app.command()
def doctor() -> None:
    """Check environment for ffmpeg and permissions."""
    ok = True
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool):
            console.print(f"[green]OK[/green] {tool} found")
        else:
            console.print(f"[red]MISSING[/red] {tool} not found in PATH")
            ok = False
    if ok:
        console.print("Environment looks good.")


if __name__ == "__main__":
    app()

