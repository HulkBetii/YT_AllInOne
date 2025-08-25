import os
import responses

from yt_allinone.src.core.exporter import download_best_thumbnail


@responses.activate
def test_thumbnail_fallback_builtin_order(tmp_path) -> None:  # type: ignore[no-untyped-def]
    vid = "abc123def45"
    base = f"https://i.ytimg.com/vi/{vid}"

    # maxresdefault 404, sddefault 200
    responses.add(responses.GET, f"{base}/maxresdefault.jpg", status=404)
    responses.add(responses.GET, f"{base}/sddefault.jpg", body=b"sdimage", status=200)
    responses.add(responses.GET, f"{base}/hqdefault.jpg", status=404)

    path = download_best_thumbnail(vid, [])
    assert path is not None
    with open(path, "rb") as fh:
        assert fh.read() == b"sdimage"
    os.remove(path)


@responses.activate
def test_thumbnail_uses_candidates_when_all_builtin_fail() -> None:  # type: ignore[no-untyped-def]
    vid = "xyz987xyz98"
    base = f"https://i.ytimg.com/vi/{vid}"
    for name in ("maxresdefault", "sddefault", "hqdefault"):
        responses.add(responses.GET, f"{base}/{name}.jpg", status=404)

    # First candidate 404, second OK
    responses.add(responses.GET, "https://example.com/a.jpg", status=404)
    responses.add(responses.GET, "https://example.com/b.jpg", body=b"ok", status=200)

    path = download_best_thumbnail(vid, [
        {"url": "https://example.com/a.jpg"},
        {"url": "https://example.com/b.jpg"},
    ])
    assert path is not None
    with open(path, "rb") as fh:
        assert fh.read() == b"ok"
    os.remove(path)


@responses.activate
def test_thumbnail_all_fail_returns_none() -> None:  # type: ignore[no-untyped-def]
    vid = "nope"
    base = f"https://i.ytimg.com/vi/{vid}"
    for name in ("maxresdefault", "sddefault", "hqdefault"):
        responses.add(responses.GET, f"{base}/{name}.jpg", status=404)

    path = download_best_thumbnail(vid, [])
    assert path is None

