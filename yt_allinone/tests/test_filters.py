from ..src.core.filters import is_shorts, is_regular, apply_filters


def test_is_shorts_by_url() -> None:
    assert is_shorts("https://www.youtube.com/shorts/abc123def45") is True
    assert is_regular("https://www.youtube.com/watch?v=abc123def45") is True


def test_is_shorts_by_duration() -> None:
    # 59s should be shorts
    entry_59 = {"webpage_url": "https://www.youtube.com/watch?v=abc123def45", "duration": 59}
    assert is_shorts(entry_59) is True

    # 61s should be regular
    entry_61 = {"webpage_url": "https://www.youtube.com/watch?v=abc123def45", "duration": 61}
    assert is_regular(entry_61) is True


def test_playlist_mixed_short_and_regular() -> None:
    playlist = [
        {"webpage_url": "https://www.youtube.com/shorts/aaa111bbb22"},
        {"webpage_url": "https://www.youtube.com/watch?v=ccc333ddd44", "duration": 45},
        {"webpage_url": "https://www.youtube.com/watch?v=eee555fff66", "duration": 600},
        {"url": "https://www.youtube.com/watch?v=ggg777hhh88"},  # no duration, not shorts URL
    ]

    shorts = apply_filters(playlist, is_shorts)
    regular = apply_filters(playlist, is_regular)

    assert len(shorts) == 2
    assert len(regular) == 2

