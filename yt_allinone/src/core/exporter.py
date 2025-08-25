from __future__ import annotations

import os
import json
import tempfile
from typing import Any, List, Iterable, Optional

import requests


def export_to_json(items: List[Any]) -> str:
    return json.dumps(items, ensure_ascii=False, indent=2)


def _attempt_download(url: str, timeout: float = 10.0) -> Optional[bytes]:
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200 and resp.content:
            return resp.content
        return None
    except Exception:
        return None


def download_best_thumbnail(video_id: str, candidates: Iterable[dict] | None = None) -> Optional[str]:
    """Try to download best available thumbnail for a video.

    Order:
      1) https://i.ytimg.com/vi/<id>/maxresdefault.jpg
      2) https://i.ytimg.com/vi/<id>/sddefault.jpg
      3) https://i.ytimg.com/vi/<id>/hqdefault.jpg
      4) Fallback to provided candidates (list of dict with 'url')

    Returns path to saved temp file, or None if all attempts fail.
    """
    base = f"https://i.ytimg.com/vi/{video_id}"
    order = [
        f"{base}/maxresdefault.jpg",
        f"{base}/sddefault.jpg",
        f"{base}/hqdefault.jpg",
    ]

    for url in order:
        data = _attempt_download(url)
        if data:
            fd, path = tempfile.mkstemp(prefix=f"{video_id}_", suffix=".jpg")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            return path

    if candidates:
        for item in candidates:
            url = item.get("url") if isinstance(item, dict) else None
            if not url:
                continue
            data = _attempt_download(url)
            if data:
                fd, path = tempfile.mkstemp(prefix=f"{video_id}_", suffix=".jpg")
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                return path

    return None


def _normalize_entry(e: Any) -> dict:
    if isinstance(e, dict):
        return e
    # Try object-like access (e.g., pydantic model)
    result: dict = {}
    for key in ("id", "title", "tags"):
        val = getattr(e, key, None)
        if val is None and hasattr(e, "raw") and isinstance(e.raw, dict):
            val = e.raw.get(key)
        result[key] = val
    return result


def export_tags(entries: Iterable[Any], outdir: str, as_csv: bool = True, as_json: bool = True) -> None:
    os.makedirs(outdir, exist_ok=True)
    csv_path = os.path.join(outdir, "tags.csv")
    json_path = os.path.join(outdir, "tags.json")

    items: List[dict] = []
    for e in entries:
        d = _normalize_entry(e)
        vid = d.get("id") or d.get("video_id") or ""
        title = d.get("title") or ""
        tags = d.get("tags") or []
        if isinstance(tags, str):
            # Some sources may have a single string; normalize to single-item list
            tags_list: List[str] = [tags]
        else:
            tags_list = [str(t) for t in (tags or [])]
        items.append({"videoId": vid, "title": title, "tags": tags_list})

    if as_csv:
        write_header = not os.path.exists(csv_path)
        with open(csv_path, "a", encoding="utf-8", newline="") as fh:
            if write_header:
                fh.write("videoId,title,tags\n")
            for it in items:
                # Escape quotes in title and wrap in quotes
                title = it["title"].replace("\"", "\"\"")
                # Comma-separated tags; ensure no newlines, wrap in quotes and escape quotes
                tags_joined = ",".join(it["tags"]).replace("\n", " ")
                tags_escaped = tags_joined.replace("\"", "\"\"")
                line = f"{it['videoId']},\"{title}\",\"{tags_escaped}\"\n"
                fh.write(line)

    if as_json:
        existing: List[dict] = []
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
                    if not isinstance(existing, list):
                        existing = []
            except Exception:
                existing = []
        existing.extend(items)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, ensure_ascii=False, indent=2)

