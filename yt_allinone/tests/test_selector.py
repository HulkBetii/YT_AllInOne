import pytest
from yt_allinone.src.core.selector import build_format_selector


@pytest.mark.parametrize(
    "quality,expected",
    [
        ("best", "bestvideo*+bestaudio/best"),
        ("1080p", "bestvideo[height<=1080]+bestaudio/best[height<=1080]"),
        ("720p", "bestvideo[height<=720]+bestaudio/best[height<=720]"),
        ("480p", "bestvideo[height<=480]+bestaudio/best[height<=480]"),
        (" Best ", "bestvideo*+bestaudio/best"),
    ],
)
def test_build_format_selector_valid(quality: str, expected: str) -> None:
    assert build_format_selector(quality) == expected


@pytest.mark.parametrize("quality", ["144p", "2k", "abc", "", None])
def test_build_format_selector_invalid(quality) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError):
        build_format_selector(quality)  # type: ignore[arg-type]

