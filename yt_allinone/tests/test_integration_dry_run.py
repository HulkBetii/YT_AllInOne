from typing import Any, Dict, List
import pytest

from ..src.download.ytdlp_wrapper import YtDlpWrapper
from ..src.core.filters import is_shorts, is_regular


class FakeYDL:
    def __init__(self, info: Dict[str, Any]) -> None:
        self.info = info

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return None

    def extract_info(self, url: str, download: bool = False) -> Dict[str, Any]:
        return self.info


def test_dry_run_filters_and_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    info = {
        "entries": [
            {"id": "v1", "title": "shorts by url", "webpage_url": "https://www.youtube.com/shorts/v1"},
            {"id": "v2", "title": "regular unknown", "webpage_url": "https://www.youtube.com/watch?v=v2"},
            {"id": "v3", "title": "short 50s", "webpage_url": "https://www.youtube.com/watch?v=v3", "duration": 50},
            {"id": "v4", "title": "regular 200s", "webpage_url": "https://www.youtube.com/watch?v=v4", "duration": 200},
        ]
    }

    monkeypatch.setattr("yt_allinone.src.download.ytdlp_wrapper.YoutubeDL", lambda params=None: FakeYDL(info))

    w = YtDlpWrapper()

    shorts = w.dry_run("https://youtube.com/playlist?list=X", filter_fn=is_shorts, limit=None)
    assert [e.id for e in shorts] == ["v1"]  # only URL-based when no limit

    regular = w.dry_run("https://youtube.com/playlist?list=X", filter_fn=is_regular, limit=10)
    assert [e.id for e in regular] == ["v2", "v4"]

    shorts2 = w.dry_run("https://youtube.com/playlist?list=X", filter_fn=is_shorts, limit=2)
    assert [e.id for e in shorts2] == ["v1", "v3"]

