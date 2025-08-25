from typing import Iterable, Callable, TypeVar, List, Any, Optional, Union

T = TypeVar("T")


def apply_filters(items: Iterable[T], *filters: Callable[[T], bool]) -> List[T]:
    result: List[T] = list(items)
    for filter_fn in filters:
        result = [item for item in result if filter_fn(item)]
    return result


def _extract_url_and_duration(entry: Union[str, Any]) -> tuple[str, Optional[float]]:
    if isinstance(entry, str):
        return entry, None

    # yt-dlp entries are dict-like. Prefer webpage_url, then url
    url: Optional[str] = None
    duration: Optional[float] = None

    try:
        url = (
            (entry.get("webpage_url") if hasattr(entry, "get") else None)
            or getattr(entry, "webpage_url", None)
            or (entry.get("url") if hasattr(entry, "get") else None)
            or getattr(entry, "url", None)
        )
        duration_val = (
            (entry.get("duration") if hasattr(entry, "get") else None)
            or getattr(entry, "duration", None)
        )
        if duration_val is not None:
            duration = float(duration_val)
    except Exception:
        url = None
        duration = None

    return url or "", duration


def is_shorts(entry: Union[str, Any]) -> bool:
    url, duration = _extract_url_and_duration(entry)
    url_lower = url.lower()
    if "/shorts/" in url_lower:
        return True
    if duration is not None and duration <= 60:
        return True
    return False


def is_regular(entry: Union[str, Any]) -> bool:
    return not is_shorts(entry)

