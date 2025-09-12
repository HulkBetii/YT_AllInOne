from typing import Any, Dict, List
import types
import pytest

from ..src.download.ytdlp_wrapper import YtDlpWrapper
from ..src.core.filters import is_shorts, is_regular


class FakeYDL:
    def __init__(self, params: Dict[str, Any] | None = None) -> None:
        self.params = params or {}
        self._info = None

    def __enter__(self) -> "FakeYDL":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    def set_info(self, info: Dict[str, Any]) -> None:
        self._info = info

    def extract_info(self, url: str, download: bool = False) -> Dict[str, Any]:
        assert self._info is not None, "FakeYDL info not set"
        return self._info


def test_list_entries_flat(monkeypatch: pytest.MonkeyPatch) -> None:
    wrapper = YtDlpWrapper()
    fake = FakeYDL()
    fake.set_info(
        {
            "entries": [
                {"id": "id1", "title": "t1", "webpage_url": "https://www.youtube.com/watch?v=id1"},
                {"id": "id2", "title": "t2", "webpage_url": "https://www.youtube.com/shorts/id2"},
            ]
        }
    )

    monkeypatch.setattr("yt_allinone.src.download.ytdlp_wrapper.YoutubeDL", lambda params=None: fake)
    entries = wrapper.list_entries("https://youtube.com/playlist?list=PLx", flat=True)
    assert len(entries) == 2
    assert entries[0].id == "id1"
    assert entries[1].url.endswith("/shorts/id2")


def test_dry_run_filter_and_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    wrapper = YtDlpWrapper()

    # First call: flat listing
    fake_flat = FakeYDL()
    fake_flat.set_info(
        {
            "entries": [
                {"id": "id1", "title": "t1", "webpage_url": "https://www.youtube.com/watch?v=id1", "duration": None},
                {"id": "id2", "title": "t2", "webpage_url": "https://www.youtube.com/shorts/id2"},
                {"id": "id3", "title": "t3", "webpage_url": "https://www.youtube.com/watch?v=id3", "duration": None},
            ]
        }
    )

    # Second call: enrich id1 and id3
    enrich_infos: List[Dict[str, Any]] = [
        {"id": "id1", "duration": 200, "title": "T1", "webpage_url": "https://www.youtube.com/watch?v=id1"},
        {"id": "id3", "duration": 50, "title": "T3", "webpage_url": "https://www.youtube.com/watch?v=id3"},
    ]
    calls = {"idx": 0}

    class FakeYDL2(FakeYDL):
        def extract_info(self, url: str, download: bool = False) -> Dict[str, Any]:
            i = calls["idx"]
            calls["idx"] += 1
            return enrich_infos[i]

    def fake_factory(params=None):
        # Return flat for first with extract_flat True, then FakeYDL2 for enrich
        if params and params.get("extract_flat"):
            return fake_flat
        return FakeYDL2(params)

    monkeypatch.setattr("yt_allinone.src.download.ytdlp_wrapper.YoutubeDL", fake_factory)

    # Only regular videos, limit 1
    out = wrapper.dry_run("https://youtube.com/playlist?list=PLx", filter_fn=is_regular, limit=1)
    assert len(out) == 1
    assert "/shorts/" not in (out[0].url or "")

    # Only shorts, no limit
    out2 = wrapper.dry_run("https://youtube.com/playlist?list=PLx", filter_fn=is_shorts, limit=None)
    assert len(out2) == 1
    assert "/shorts/" in (out2[0].url or "")

