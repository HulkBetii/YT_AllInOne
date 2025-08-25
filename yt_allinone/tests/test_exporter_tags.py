import json
import os
from pathlib import Path

from yt_allinone.src.core.exporter import export_tags


def test_export_tags_unicode_and_empty(tmp_path: Path) -> None:
    entries = [
        {"id": "vid1", "title": "Bài hát ❤️", "tags": ["nhạc trẻ", "Việt Nam"]},
        {"id": "vid2", "title": "No Tags", "tags": []},
        {"id": "vid3", "title": "One Tag", "tags": ["tag"]},
    ]

    outdir = tmp_path.as_posix()
    export_tags(entries, outdir, as_csv=True, as_json=True)

    # Append again to test accumulation
    export_tags([{"id": "vid4", "title": "追加", "tags": ["日本語", "テスト"]}], outdir)

    # Verify CSV
    csv_path = os.path.join(outdir, "tags.csv")
    with open(csv_path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    assert lines[0] == "videoId,title,tags"
    assert any("vid1" in line and "Bài hát" in line and "nhạc trẻ;Việt Nam" in line for line in lines)
    assert any("vid2" in line and ",\"No Tags\"," in line for line in lines)
    assert any("vid4" in line and "追加" in line and "日本語;テスト" in line for line in lines)

    # Verify JSON
    json_path = os.path.join(outdir, "tags.json")
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    ids = [d["videoId"] for d in data]
    assert ids == ["vid1", "vid2", "vid3", "vid4"]

