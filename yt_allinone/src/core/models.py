from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from enum import Enum


class DownloadItem(BaseModel):
    url: str
    title: Optional[str] = None
    formats: Optional[List[str]] = None


class VideoEntry(BaseModel):
    id: str
    url: str
    title: Optional[str] = None
    duration: Optional[float] = None
    thumbnails: Optional[List[dict]] = None
    tags: Optional[List[str]] = None
    webpage_url: Optional[str] = None
    raw: Optional[Any] = Field(default=None, description="Original yt-dlp entry")


class DownloadTask(BaseModel):
    url: str
    outdir: str
    quality: str = "best"
    only_audio: bool = False
    cookies_from_browser: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class ErrorCode(str, Enum):
    PRIVATE = "PRIVATE"
    GEO_BLOCK = "GEO_BLOCK"
    AGE_GATE = "AGE_GATE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    CONTENT_UNAVAILABLE = "CONTENT_UNAVAILABLE"
    VIDEO_UNAVAILABLE = "VIDEO_UNAVAILABLE"
    NETWORK = "NETWORK"
    FFMPEG_MISSING = "FFMPEG_MISSING"
    NO_SPACE = "NO_SPACE"
    UNKNOWN = "UNKNOWN"


class DownloadError(Exception):
    def __init__(self, code: ErrorCode, message: str, hint: Optional[str] = None):
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(message)

