from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable
from loguru import logger
from yt_dlp import YoutubeDL

from ..core.models import VideoEntry, DownloadError, ErrorCode
from ..core.filters import is_shorts, is_regular
from ..utils.text_utils import clean_ansi_codes


class YtDlpWrapper:
    def __init__(self, options: Optional[Dict[str, Any]] = None) -> None:
        self.options = options or {}

    def _build_ydl(self, opts: Optional[Dict[str, Any]] = None) -> YoutubeDL:
        final_opts: Dict[str, Any] = {
            "quiet": True,
            "noplaylist": False,
            "nocheckcertificate": True,
            "skip_download": True,
        }
        final_opts.update(self.options)
        if opts:
            final_opts.update(opts)
        return YoutubeDL(params=final_opts)

    def list_entries(self, url: str, cookies: Optional[str] = None, flat: bool = True) -> List[VideoEntry]:
        opts: Dict[str, Any] = {}
        if cookies:
            opts["cookiesfrombrowser"] = (cookies,)
        if flat:
            # Use flat playlist to list quickly
            opts["extract_flat"] = True
        entries: List[VideoEntry] = []
        
        # Try with cookies first, then without if cookies fail
        try:
            with self._build_ydl(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            # If cookies failed and we were using them, try without cookies
            if cookies and "could not copy" in str(exc).lower():
                try:
                    opts_no_cookies = opts.copy()
                    opts_no_cookies.pop("cookiesfrombrowser", None)
                    with self._build_ydl(opts_no_cookies) as ydl:
                        info = ydl.extract_info(url, download=False)
                except Exception as exc2:
                    raise self._map_error(exc2)
            else:
                raise self._map_error(exc)

        if info is None:
            return []
        if "entries" in info and isinstance(info["entries"], list):
            raw_entries = info["entries"]
        else:
            raw_entries = [info]

        for e in raw_entries:
            vid = e.get("id") if hasattr(e, "get") else None
            webpage_url = (e.get("webpage_url") if hasattr(e, "get") else None) or (
                f"https://www.youtube.com/watch?v={vid}" if vid else None
            )
            entry = VideoEntry(
                id=vid or "",
                url=webpage_url or "",
                title=(e.get("title") if hasattr(e, "get") else None),
                duration=(e.get("duration") if hasattr(e, "get") else None),
                thumbnails=(e.get("thumbnails") if hasattr(e, "get") else None),
                tags=(e.get("tags") if hasattr(e, "get") else None),
                webpage_url=webpage_url,
                raw=e,
            )
            entries.append(entry)

        return entries

    def enrich_entry(self, entry: VideoEntry) -> VideoEntry:
        if entry.duration is not None and entry.title is not None:
            return entry
        try:
            with self._build_ydl({"extract_flat": False}) as ydl:
                info = ydl.extract_info(entry.url or entry.webpage_url or entry.id, download=False)
        except Exception as exc:
            raise self._map_error(exc)
        entry.duration = info.get("duration")
        entry.title = info.get("title")
        entry.thumbnails = info.get("thumbnails")
        entry.tags = info.get("tags")
        entry.webpage_url = info.get("webpage_url") or entry.webpage_url
        entry.url = entry.webpage_url or entry.url
        entry.raw = info
        return entry

    def dry_run(
        self,
        url: str,
        filter_fn: Optional[Callable[[VideoEntry], bool]] = None,
        limit: Optional[int] = None,
        cookies: Optional[str] = None,
    ) -> List[VideoEntry]:
        entries = self.list_entries(url, cookies=cookies, flat=True)

        if filter_fn is None:
            return entries[: max(0, int(limit))] if limit is not None else entries

        # Special-case optimization for shorts: prefer URL-based detection first
        if filter_fn is is_shorts:
            url_shorts: List[VideoEntry] = [
                e for e in entries if "/shorts/" in (e.url or e.webpage_url or "").lower()
            ]
            if limit is None:
                # No limit requested: return only URL-based shorts without enrichment
                return url_shorts
            # With limit: fill with URL-based first
            if len(url_shorts) >= int(limit):
                return url_shorts[: int(limit)]

            # Need more: enrich remaining to detect duration-based shorts
            remaining_needed = int(limit) - len(url_shorts)
            result: List[VideoEntry] = list(url_shorts)
            for e in entries:
                if e in url_shorts:
                    continue
                enriched = self.enrich_entry(e)
                if is_shorts({"webpage_url": enriched.url, "duration": enriched.duration}):
                    result.append(enriched)
                    if len(result) >= int(limit):
                        break
            return result

        # Regular videos: exclude shorts (by URL and possibly by duration)
        result_regular: List[VideoEntry] = []
        if limit is None:
            # No limit: enrich as needed to correctly exclude duration-based shorts
            for e in entries:
                base_is_short = "/shorts/" in (e.url or e.webpage_url or "").lower()
                enriched = e if base_is_short else self.enrich_entry(e)
                if is_regular({"webpage_url": enriched.url, "duration": enriched.duration}):
                    result_regular.append(enriched)
            return result_regular
        else:
            for e in entries:
                if len(result_regular) >= int(limit):
                    break
                base_is_short = "/shorts/" in (e.url or e.webpage_url or "").lower()
                enriched = e if base_is_short else self.enrich_entry(e)
                if is_regular({"webpage_url": enriched.url, "duration": enriched.duration}):
                    result_regular.append(enriched)
            return result_regular

    def _map_error(self, exc: Exception) -> DownloadError:
        msg = str(exc)
        # Clean up ANSI escape codes that cause display issues in GUI
        msg = clean_ansi_codes(msg)
        
        lower = msg.lower()
        
        # Content not available (outdated yt-dlp)
        if "not available on this app" in lower and "latest version of youtube" in lower:
            return DownloadError(
                code=ErrorCode.CONTENT_UNAVAILABLE, 
                message=msg, 
                hint="yt-dlp cần cập nhật. Chạy: pip install --upgrade yt-dlp"
            )
        
        # Video unavailable
        if "video unavailable" in lower:
            return DownloadError(
                code=ErrorCode.VIDEO_UNAVAILABLE, 
                message=msg, 
                hint="Video không khả dụng hoặc đã bị xoá. Thử URL khác."
            )
        
        # Authentication required (bot check)
        if "sign in to confirm" in lower and "not a bot" in lower:
            return DownloadError(
                code=ErrorCode.AUTH_REQUIRED, 
                message=msg, 
                hint="YouTube yêu cầu xác thực. Dùng --cookies-from-browser chrome/edge/firefox hoặc --cookies file.txt"
            )
        
        # Cookie database access error
        if "could not copy" in lower and "cookie database" in lower:
            return DownloadError(
                code=ErrorCode.AUTH_REQUIRED,
                message=msg,
                hint="Trình duyệt đang chạy, đóng Chrome/Edge rồi thử lại, hoặc chọn trình duyệt khác (Firefox/Safari)"
            )
        
        # Network / retryable
        if any(k in lower for k in ["temporary failure", "timed out", "connection", "read error", "http error 5"]):
            return DownloadError(code=ErrorCode.NETWORK, message=msg, hint="Kiểm tra mạng và thử lại.")
        
        # Private/removed (403/410)
        if "http error 403" in lower or "http error 410" in lower or "private" in lower:
            return DownloadError(code=ErrorCode.PRIVATE, message=msg, hint="Video riêng tư/đã xoá. Cần quyền hoặc URL khác.")
        
        # Geo block
        if "not available in your country" in lower or "geo" in lower:
            return DownloadError(code=ErrorCode.GEO_BLOCK, message=msg, hint="Bật geo_bypass hoặc dùng cookies phù hợp vùng.")
        
        # Age gate
        if "age" in lower and ("verify" in lower or "gate" in lower or "consent" in lower):
            return DownloadError(code=ErrorCode.AGE_GATE, message=msg, hint="Dùng cookies-from-browser để vượt qua age gate.")
        
        # No space
        if "no space" in lower or "no space left" in lower or "disk full" in lower:
            return DownloadError(code=ErrorCode.NO_SPACE, message=msg, hint="Giải phóng dung lượng ổ đĩa.")
        
        # HTTP errors (404, etc.)
        if "http error" in lower:
            return DownloadError(code=ErrorCode.UNKNOWN, message=msg, hint="URL không hợp lệ hoặc không tồn tại.")
        
        # Fallback
        return DownloadError(code=ErrorCode.UNKNOWN, message=msg, hint="Thử lại với tuỳ chọn khác hoặc kiểm tra log.")

