_LANG = "vi"

_STRINGS = {
    "vi": {
        "app.title": "yt-allinone",
        "menu.view": "Xem",
        "menu.language": "Ngôn ngữ",
        "lang.vi": "Tiếng Việt",
        "lang.en": "English",

        "source.group": "Nguồn",
        "link.placeholder": "https://youtu.be/..., /watch?v=..., /playlist?list=..., /@handle…",
        "btn.paste": "Dán",
        "btn.detect": "Nhận diện",
        "folder": "Thư mục:",
        "btn.browse": "Chọn...",
        "quality": "Chất lượng:",
        "quality.tt": "Chất lượng: best → 'bestvideo*+bestaudio/best'; 1080p/720p/480p dùng selector tương ứng.",
        "filter": "Lọc:",
        "limit": "Giới hạn:",
        "opt.thumb": "Tải thumbnail",
        "opt.subs": "Tải phụ đề/Không tải video",
        "opt.subs.tt": "Chế độ chỉ liệt kê và tải phụ đề nếu có.",
        "opt.tags": "Tải thẻ Tag (export tags)",
        "opt.tags.tt": "Xuất tags sang CSV/JSON sau khi tải xong.",
        "opt.audio": "Chỉ tải MP3",
        "opt.audio.tt": "Sẽ trích âm thanh bằng ffmpeg và gắn metadata",

        "btn.start": "Bắt đầu",
        "btn.pause": "Tạm dừng",
        "btn.resume": "Tiếp tục",
        "btn.stop": "Kết thúc",
        "btn.list": "Liệt kê (Dry-run)",

        "title.total": "Tiến độ tổng:",
        "title.current": "Tiến độ hiện tại:",
        "title.log": "Nhật ký:",
    },
    "en": {
        "app.title": "yt-allinone",
        "menu.view": "View",
        "menu.language": "Language",
        "lang.vi": "Vietnamese",
        "lang.en": "English",

        "source.group": "Source",
        "link.placeholder": "https://youtu.be/..., /watch?v=..., /playlist?list=..., /@handle…",
        "btn.paste": "Paste",
        "btn.detect": "Detect",
        "folder": "Folder:",
        "btn.browse": "Browse...",
        "quality": "Quality:",
        "quality.tt": "Quality: best → 'bestvideo*+bestaudio/best'; 1080p/720p/480p use mapped selectors.",
        "filter": "Filter:",
        "limit": "Limit:",
        "opt.thumb": "Download thumbnail",
        "opt.subs": "Download subtitles / No video",
        "opt.subs.tt": "List and download subtitles only if available.",
        "opt.tags": "Download tags (export)",
        "opt.tags.tt": "Export tags to CSV/JSON after completion.",
        "opt.audio": "Audio only",
        "opt.audio.tt": "Extract audio via ffmpeg and write metadata",

        "btn.start": "Start",
        "btn.pause": "Pause",
        "btn.resume": "Resume",
        "btn.stop": "Stop",
        "btn.list": "List (Dry-run)",

        "title.total": "Overall progress:",
        "title.current": "Current progress:",
        "title.log": "Logs:",
    },
}


def set_language(lang: str) -> None:
    global _LANG
    _LANG = "en" if lang == "en" else "vi"


def get_language() -> str:
    return _LANG


def tr(key: str) -> str:
    table = _STRINGS.get(_LANG, _STRINGS["vi"])  # default vi
    return table.get(key, key)

