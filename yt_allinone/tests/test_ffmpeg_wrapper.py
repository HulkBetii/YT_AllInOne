import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ..src.download.ffmpeg_wrapper import extract_mp3, FFmpegError


ffmpeg = shutil.which("ffmpeg")
ffprobe = shutil.which("ffprobe")


@pytest.mark.skipif(not (ffmpeg and ffprobe), reason="ffmpeg/ffprobe not available")
def test_extract_mp3_without_cover(tmp_path: Path) -> None:
    # Generate tiny sine wave audio in mp4 container
    input_path = tmp_path / "in.mp4"
    mp3_path = tmp_path / "out.mp3"
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:duration=1",
        str(input_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    extract_mp3(str(input_path), str(mp3_path), {"title": "T", "artist": "A"})
    assert mp3_path.exists()


@pytest.mark.skipif(not (ffmpeg and ffprobe), reason="ffmpeg/ffprobe not available")
def test_extract_mp3_with_cover(tmp_path: Path) -> None:
    # Create tiny audio and a cover image
    input_path = tmp_path / "in2.mp4"
    mp3_path = tmp_path / "out2.mp3"
    cover = tmp_path / "cover.jpg"

    # Generate 1s sine audio
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=800:duration=1", str(input_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Generate a small cover (solid color)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=red:s=64x64", "-frames:v", "1", str(cover)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    extract_mp3(str(input_path), str(mp3_path), {"title": "Song", "artist": "Channel"}, str(cover))
    assert mp3_path.exists()


def test_extract_mp3_missing_input(tmp_path: Path) -> None:
    with pytest.raises(FFmpegError):
        extract_mp3(str(tmp_path / "no.mp4"), str(tmp_path / "out.mp3"), {"title": "X"})

