import importlib
import pytest
from ..src.core.url_parser import parse_input, Kind, ParsedInput


def test_imports() -> None:
    modules = [
        "yt_allinone.src.app_cli",
        "yt_allinone.src.app_gui",
        "yt_allinone.src.core.models",
        "yt_allinone.src.core.url_parser",
        "yt_allinone.src.core.selector",
        "yt_allinone.src.core.filters",
        "yt_allinone.src.core.exporter",
        "yt_allinone.src.download.ytdlp_wrapper",
        "yt_allinone.src.download.ffmpeg_wrapper",
        "yt_allinone.src.download.queue",
        "yt_allinone.src.ui.main_window",
        "yt_allinone.src.ui.widgets",
        "yt_allinone.src.utils.log",
        "yt_allinone.src.utils.config",
    ]

    for m in modules:
        importlib.import_module(m)


@pytest.mark.parametrize(
    "raw,kind,canonical",
    [
        # VIDEO: youtu.be
        ("https://youtu.be/dQw4w9WgXcQ", Kind.VIDEO, "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("youtu.be/dQw4w9WgXcQ", Kind.VIDEO, "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        # VIDEO: watch?v
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", Kind.VIDEO, "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("http://youtube.com/watch?v=dQw4w9WgXcQ&ab_channel=Rick", Kind.VIDEO, "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        # VIDEO: shorts
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", Kind.VIDEO, "https://www.youtube.com/shorts/dQw4w9WgXcQ"),
        ("youtube.com/shorts/dQw4w9WgXcQ?feature=share", Kind.VIDEO, "https://www.youtube.com/shorts/dQw4w9WgXcQ"),
        # PLAYLIST
        ("https://www.youtube.com/playlist?list=PL1234567890", Kind.PLAYLIST, "https://www.youtube.com/playlist?list=PL1234567890"),
        ("youtube.com/playlist?list=PLabcdefghij", Kind.PLAYLIST, "https://www.youtube.com/playlist?list=PLabcdefghij"),
        # CHANNEL by ID
        ("https://www.youtube.com/channel/UCabcdefghijklmno1234567", Kind.CHANNEL, "https://www.youtube.com/channel/UCabcdefghijklmno1234567/videos"),
        ("youtube.com/channel/UCabcdefghijklmno1234567/about", Kind.CHANNEL, "https://www.youtube.com/channel/UCabcdefghijklmno1234567/videos"),
        # HANDLE page
        ("https://www.youtube.com/@some_handle", Kind.HANDLE, "https://www.youtube.com/@some_handle/videos"),
        ("www.youtube.com/@Some.Handle/videos", Kind.HANDLE, "https://www.youtube.com/@some.handle/videos"),
        # Bare handle
        ("@MyHandle", Kind.HANDLE, "https://www.youtube.com/@myhandle/videos"),
    ],
)
def test_parse_valid_cases(raw: str, kind: Kind, canonical: str) -> None:
    parsed = parse_input(raw)
    assert parsed is not None
    assert isinstance(parsed, ParsedInput)
    assert parsed.kind == kind
    assert parsed.canonical_url == canonical
    assert parsed.raw == raw


@pytest.mark.parametrize(
    "raw",
    [
        "",  # empty
        "not a url",
        "https://example.com/watch?v=dQw4w9WgXcQ",  # wrong domain
        "https://youtube.com/watch?v=short",  # invalid video id
        "https://youtu.be/short",  # invalid short id
        "https://youtube.com/playlist?list=too_short",  # invalid list id
        "https://youtube.com/channel/UCshort",  # invalid channel id
        "@x",  # too short handle
        "/@handle with space",  # invalid characters
        "https://youtube.com/@",  # empty handle
    ],
)
def test_parse_invalid_cases(raw: str) -> None:
    assert parse_input(raw) is None

