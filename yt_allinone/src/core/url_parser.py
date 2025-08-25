import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Kind(str, Enum):
    VIDEO = "VIDEO"
    PLAYLIST = "PLAYLIST"
    CHANNEL = "CHANNEL"
    HANDLE = "HANDLE"


@dataclass(frozen=True)
class ParsedInput:
    kind: Kind
    canonical_url: str
    raw: str


_VIDEO_ID_RE = r"(?P<vid>[A-Za-z0-9_-]{11})"
_LIST_ID_RE = r"(?P<list>[A-Za-z0-9_-]{10,})"
_CHANNEL_ID_RE = r"(?P<chid>UC[A-Za-z0-9_-]{22})"
_HANDLE_RE = r"(?P<handle>@[A-Za-z0-9._-]{3,30})"

# Domains
_YOUTUBE_HOST_RE = r"(?:www\.|m\.)?youtube\.com"
_YOUTU_BE_HOST_RE = r"youtu\.be"


def _strip(s: str) -> str:
    return s.strip()


def parse_input(raw: str) -> Optional[ParsedInput]:
    """Parse and canonicalize YouTube inputs.

    Accepts: youtu.be/..., youtube.com/watch?v=..., /playlist?list=..., /channel/UC..., /@handle, /shorts/...
    Returns ParsedInput(kind, canonical_url, raw) or None if not recognized.
    """
    if not raw or not raw.strip():
        return None

    s = _strip(raw)

    # 1) Bare handle like @name
    m = re.fullmatch(_HANDLE_RE, s, flags=re.IGNORECASE)
    if m:
        handle = m.group("handle").lower()
        return ParsedInput(Kind.HANDLE, f"https://www.youtube.com/{handle}/videos", raw)

    # Normalize to make regex matching easier
    # youtu.be short links -> treat as url
    # 2) youtu.be/{video}
    m = re.match(
        rf"^(?:https?://)?{_YOUTU_BE_HOST_RE}/({_VIDEO_ID_RE})(?:[/?#].*)?$",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        vid = m.group("vid")
        return ParsedInput(Kind.VIDEO, f"https://www.youtube.com/watch?v={vid}", raw)

    # 3) youtube.com/watch?v=VIDEO
    m = re.match(
        rf"^(?:https?://)?{_YOUTUBE_HOST_RE}/watch\?(?:.*&)?v={_VIDEO_ID_RE}(?:[&#/].*)?$",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        vid = m.group("vid")
        return ParsedInput(Kind.VIDEO, f"https://www.youtube.com/watch?v={vid}", raw)

    # 4) youtube.com/shorts/VIDEO
    m = re.match(
        rf"^(?:https?://)?{_YOUTUBE_HOST_RE}/shorts/{_VIDEO_ID_RE}(?:[/?#].*)?$",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        vid = m.group("vid")
        # Keep as shorts canonical; still classified as VIDEO
        return ParsedInput(Kind.VIDEO, f"https://www.youtube.com/shorts/{vid}", raw)

    # 5) youtube.com/playlist?list=LIST
    m = re.match(
        rf"^(?:https?://)?{_YOUTUBE_HOST_RE}/playlist\?(?:.*&)?list={_LIST_ID_RE}(?:[&#/].*)?$",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        pl = m.group("list")
        return ParsedInput(Kind.PLAYLIST, f"https://www.youtube.com/playlist?list={pl}", raw)

    # 6) youtube.com/channel/UC...
    m = re.match(
        rf"^(?:https?://)?{_YOUTUBE_HOST_RE}/channel/{_CHANNEL_ID_RE}(?:/.*)?$",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        chid = m.group("chid")
        return ParsedInput(Kind.CHANNEL, f"https://www.youtube.com/channel/{chid}/videos", raw)

    # 7) youtube.com/@handle (optionally with /videos)
    m = re.match(
        rf"^(?:https?://)?{_YOUTUBE_HOST_RE}/({_HANDLE_RE})(?:/videos)?(?:[/?#].*)?$",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        handle = m.group("handle").lower()
        return ParsedInput(Kind.HANDLE, f"https://www.youtube.com/{handle}/videos", raw)

    return None
from typing import Optional
from urllib.parse import urlparse


def parse_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    return parsed.netloc or None

