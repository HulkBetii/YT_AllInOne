from typing import Iterable, Callable, TypeVar, List

T = TypeVar("T")


def select(items: Iterable[T], predicate: Callable[[T], bool]) -> List[T]:
    return [i for i in items if predicate(i)]


def build_format_selector(quality: str) -> str:
    q = (quality or "").strip().lower()
    mapping = {
        "best": "bestvideo*+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    }
    if q in mapping:
        return mapping[q]
    raise ValueError(f"Unsupported quality: {quality}")

