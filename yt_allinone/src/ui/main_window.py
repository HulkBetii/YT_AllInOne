from __future__ import annotations

import os
from typing import Optional, Callable, List, Dict, Any

from PySide6.QtCore import Qt, QObject, Signal, QThread, QSettings
from PySide6.QtGui import QIcon, QTextCursor, QKeySequence, QFontDatabase, QShortcut, QTextOption
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QProgressBar,
    QPlainTextEdit,
    QGroupBox,
    QFormLayout,
    QDialog,
    QTableView,
    QHeaderView,
    QFrame,
    QMessageBox,
    QStyle,
    QMenu,
    QLineEdit as QSearchLineEdit,
)
from PySide6.QtGui import QAction as GuiAction  # noqa: F401 (not used directly; retained for compatibility)

from ..core.selector import build_format_selector
from ..core.filters import is_shorts, is_regular
from ..core.exporter import download_best_thumbnail, export_tags
from ..core.models import DownloadTask
from ..download.ytdlp_wrapper import YtDlpWrapper
from ..download.queue import DownloadManager
from ..utils.config import get_default_download_dir
from ..utils.i18n import tr, set_language, get_language


class ProgressSignal(QObject):
    progress = Signal(dict)
    message = Signal(str)
    done = Signal()
    error = Signal(str)


class DownloadThread(QThread):
    def __init__(self, url: str, outdir: str, quality: str, only_audio: bool, only_shorts: bool, only_regular: bool, limit: Optional[int], thumb: bool, export_tags_flag: bool, cookies_from_browser: Optional[str]) -> None:
        super().__init__()
        self.url = url
        self.outdir = outdir
        self.quality = quality
        self.only_audio = only_audio
        self.only_shorts = only_shorts
        self.only_regular = only_regular
        self.limit = limit
        self.thumb = thumb
        self.export_tags_flag = export_tags_flag
        self.cookies_from_browser = cookies_from_browser
        self.signals = ProgressSignal()
        self.manager = DownloadManager()
        self.manager.on_progress(self._on_progress)
        self.stop_after_current: bool = False
        self.total_count: int = 0
        self.completed_items: int = 0

    def _on_progress(self, ev: Dict[str, Any]) -> None:
        self.signals.progress.emit(ev)

    def run(self) -> None:  # type: ignore[override]
        try:
            filter_fn: Optional[Callable[[Any], bool]] = None
            if self.only_shorts and self.only_regular:
                raise ValueError("Chọn một trong Chỉ Shorts hoặc Chỉ video thường")
            if self.only_shorts:
                filter_fn = is_shorts
            elif self.only_regular:
                filter_fn = is_regular

            ydl_opts: Dict[str, Any] = {"geo_bypass": True}
            if self.cookies_from_browser:
                ydl_opts["cookiesfrombrowser"] = (self.cookies_from_browser,)
            wrapper = YtDlpWrapper(options=ydl_opts)

            # Try with cookies first, then without if cookies fail
            try:
                entries = wrapper.dry_run(self.url, filter_fn=filter_fn, limit=self.limit, cookies=self.cookies_from_browser)
            except Exception as exc:
                if self.cookies_from_browser and "could not copy" in str(exc).lower():
                    self.signals.message.emit("Không thể truy cập cookies, thử tải không cookies...")
                    entries = wrapper.dry_run(self.url, filter_fn=filter_fn, limit=self.limit, cookies=None)
                else:
                    raise exc
            if not entries:
                self.signals.error.emit("Không tìm thấy video nào để tải")
                return
                
            self.total_count = len(entries)
            self.signals.message.emit(f"Tìm thấy {self.total_count} video để tải")
            
            if self.thumb:
                os.makedirs(self.outdir, exist_ok=True)
                for e in entries:
                    try:
                        path = download_best_thumbnail(e.id, e.raw.get("thumbnails") if e.raw else None)
                        if path:
                            dest = os.path.join(self.outdir, f"{e.id}.jpg")
                            try:
                                os.replace(path, dest)
                                self.signals.message.emit(f"Đã tải thumbnail: {dest}")
                            except Exception:
                                pass
                    except Exception as ex:
                        self.signals.message.emit(f"Lỗi tải thumbnail cho {e.id}: {ex}")

            for e in entries:
                if self.stop_after_current:
                    break
                    
                fmt = build_format_selector(self.quality)
                task = DownloadTask(url=e.url or e.webpage_url or f"https://www.youtube.com/watch?v={e.id}", outdir=self.outdir, quality=self.quality, only_audio=self.only_audio, cookies_from_browser=self.cookies_from_browser, options={"format": fmt})
                self.signals.message.emit(f"Đang tải: {task.url}")
                
                try:
                    self.manager.start(task)
                    # Wait for the download to complete
                    while self.manager.is_running():
                        self.msleep(100)  # Sleep for 100ms to avoid blocking
                    # update overall after each item finishes
                    self.completed_items += 1
                    if self.total_count:
                        overall_pct = int(self.completed_items * 100 / self.total_count)
                        self.signals.progress.emit({"event": "overall", "overall_percent": overall_pct})
                    self.signals.message.emit(f"Hoàn thành tải video {self.completed_items}/{self.total_count}")
                except Exception as ex:
                    self.signals.error.emit(f"Lỗi tải video {e.id}: {ex}")

            if self.export_tags_flag:
                try:
                    export_tags((e.raw or {"id": e.id, "title": e.title, "tags": e.raw.get("tags") if e.raw else []} for e in entries), self.outdir)
                    self.signals.message.emit("Đã xuất tags thành công")
                except Exception as ex:
                    self.signals.error.emit(f"Lỗi xuất tags: {ex}")

            self.signals.done.emit()
        except Exception as exc:  # pragma: no cover
            self.signals.error.emit(str(exc))

    def pause(self) -> None:
        self.manager.pause()

    def resume(self) -> None:
        self.manager.resume()

    def cancel(self) -> None:
        # Soft cancel: mark to stop after current
        self.stop_after_current = True


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(tr("app.title"))
        try:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "assets", "icon.png")
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        self.worker: Optional[DownloadThread] = None
        self._state: str = "idle"

        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Input group
        self.input_group = QGroupBox()
        form = QFormLayout(self.input_group)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://youtu.be/..., /watch?v=..., /playlist?list=..., /@handle…")
        # Link row with actions: Paste, Detect, and chip label
        link_row = QWidget()
        link_row_lay = QHBoxLayout(link_row)
        link_row_lay.setContentsMargins(12, 12, 12, 12)
        link_row_lay.setSpacing(8)
        self.btn_paste = QPushButton("Dán")
        self.btn_paste.setToolTip("Dán từ clipboard (Ctrl+V)")
        self.btn_paste.setShortcut(QKeySequence.Paste)
        self.btn_detect = QPushButton("Nhận diện")
        self.btn_detect.setToolTip("Phân loại và chuẩn hoá liên kết")
        self.kind_chip = QLabel("")
        self.kind_chip.setVisible(False)
        self.kind_chip.setStyleSheet(
            "QLabel { background-color: #3aa3e3; color: white; border-radius: 8px; padding: 2px 6px; }"
        )
        link_row_lay.addWidget(self.url_edit, 1)
        link_row_lay.addWidget(self.btn_paste)
        link_row_lay.addWidget(self.btn_detect)
        link_row_lay.addWidget(self.kind_chip)
        self.out_edit = QLineEdit(get_default_download_dir())
        self.browse_btn = QPushButton("Chọn...")
        out_layout = QHBoxLayout()
        out_layout.setContentsMargins(12, 12, 12, 12)
        out_layout.setSpacing(8)
        out_container = QWidget()
        out_layout.setContentsMargins(0, 0, 0, 0)
        out_layout.addWidget(self.out_edit)
        out_layout.addWidget(self.browse_btn)
        out_container.setLayout(out_layout)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["best", "1080p", "720p", "480p"])
        self.quality_combo.setToolTip("Chất lượng tải: best → 'bestvideo*+bestaudio/best'; 1080p/720p/480p dùng selector tương ứng.")
        
        self.cookie_combo = QComboBox()
        self.cookie_combo.addItems(["Không dùng", "Chrome", "Edge", "Firefox", "Safari"])
        self.cookie_combo.setToolTip("Chọn trình duyệt để lấy cookies xác thực YouTube\nLưu ý: Đóng trình duyệt trước khi tải để tránh lỗi cookie database")
        
        self.chk_only_shorts = QCheckBox("Chỉ Shorts")
        self.chk_only_regular = QCheckBox("Chỉ video thường")
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 10000)
        self.spin_limit.setValue(10)
        self.chk_thumb = QCheckBox("Tải thumbnail")
        self.chk_subs = QCheckBox("Tải phụ đề/Không tải video")
        self.chk_subs.setToolTip("Chế độ chỉ liệt kê và tải phụ đề nếu có.")
        self.chk_tags = QCheckBox("Tải thẻ Tag (export tags)")
        self.chk_tags.setToolTip("Xuất tags sang CSV/JSON sau khi tải xong.")
        self.chk_audio = QCheckBox("Chỉ tải MP3")
        self.chk_audio.setToolTip("Sẽ trích âm thanh bằng ffmpeg và gắn metadata")

        # Row labels for i18n
        self.lbl_link = QLabel()
        self.lbl_folder = QLabel()
        self.lbl_quality = QLabel()
        self.lbl_cookies = QLabel()
        self.lbl_filter = QLabel()
        self.lbl_limit = QLabel()
        self.lbl_options = QLabel("Tuỳ chọn:")
        form.addRow(self.lbl_link, link_row)
        form.addRow(self.lbl_folder, out_container)
        form.addRow(self.lbl_quality, self.quality_combo)
        form.addRow(self.lbl_cookies, self.cookie_combo)
        form.addRow(self.lbl_filter, self._row([self.chk_only_shorts, self.chk_only_regular]))
        form.addRow(self.lbl_limit, self.spin_limit)
        form.addRow(self.lbl_options, self._row([self.chk_thumb, self.chk_subs, self.chk_tags, self.chk_audio]))

        # Controls
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setContentsMargins(12, 12, 12, 12)
        ctrl_layout.setSpacing(8)
        self.btn_start = QPushButton()
        self.btn_start.setObjectName("primary")
        self.btn_pause = QPushButton()
        self.btn_pause.setObjectName("warning")
        self.btn_cancel = QPushButton()
        self.btn_cancel.setObjectName("danger")
        self.btn_list = QPushButton()
        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addWidget(self.btn_pause)
        ctrl_layout.addWidget(self.btn_cancel)
        ctrl_layout.addWidget(self.btn_list)

        # Progress and log
        self.total_progress = QProgressBar()
        self.total_progress.setRange(0, 100)
        self.total_progress_label = QLabel("")
        self.total_progress_label.setVisible(False)

        self.item_progress = QProgressBar()
        self.item_progress.setRange(0, 100)
        self.item_progress_label = QLabel("")
        self.item_progress_label.setVisible(False)
        # Search bar above log (hidden by default)
        self.log_search = QSearchLineEdit()
        self.log_search.setPlaceholderText("Tìm trong nhật ký… (Enter để tìm tiếp)")
        self.log_search.setVisible(False)
        self.log_search.returnPressed.connect(self._find_next)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)
        self.log.setWordWrapMode(QTextOption.NoWrap)
        self.log.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.log.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log.customContextMenuRequested.connect(self._log_context_menu)

        # Shortcut Ctrl+F to toggle search bar
        self.shortcut_find = QShortcut(QKeySequence.Find, self)
        self.shortcut_find.activated.connect(self._toggle_search)
        # App shortcuts
        self.shortcut_start = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_start.activated.connect(self._start)
        self.shortcut_pause = QShortcut(QKeySequence("Space"), self)
        self.shortcut_pause.activated.connect(self._pause)
        self.shortcut_stop = QShortcut(QKeySequence("Esc"), self)
        self.shortcut_stop.activated.connect(self._cancel)

        root.addWidget(self.input_group)
        root.addLayout(ctrl_layout)
        self.lbl_total = QLabel()
        root.addWidget(self.lbl_total)
        total_row = QHBoxLayout()
        total_row.setContentsMargins(12, 12, 12, 12)
        total_row.setSpacing(8)
        total_row.addWidget(self.total_progress, 1)
        total_row.addWidget(self.total_progress_label)
        root.addLayout(total_row)

        self.lbl_current = QLabel()
        root.addWidget(self.lbl_current)
        item_row = QHBoxLayout()
        item_row.setContentsMargins(12, 12, 12, 12)
        item_row.setSpacing(8)
        item_row.addWidget(self.item_progress, 1)
        item_row.addWidget(self.item_progress_label)
        root.addLayout(item_row)

        # Error banner (hidden by default)
        self.error_banner = QFrame()
        self.error_banner.setFrameShape(QFrame.StyledPanel)
        self.error_banner.setStyleSheet(
            "QFrame { background: #c0392b; color: white; border-radius: 6px; } QPushButton { background: transparent; color: white; }"
        )
        self.error_banner.setVisible(False)
        err_lay = QHBoxLayout(self.error_banner)
        err_lay.setContentsMargins(12, 8, 12, 8)
        err_lay.setSpacing(8)
        self.err_icon = QLabel()
        pm = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning).pixmap(20, 20)
        self.err_icon.setPixmap(pm)
        self.err_msg = QLabel("")
        self.err_msg.setWordWrap(True)
        self.err_details_btn = QPushButton("Chi tiết…")
        self.err_hide_btn = QPushButton("Ẩn")
        err_lay.addWidget(self.err_icon)
        err_lay.addWidget(self.err_msg, 1)
        err_lay.addWidget(self.err_details_btn)
        err_lay.addWidget(self.err_hide_btn)
        root.addWidget(self.error_banner)
        self.lbl_log = QLabel()
        root.addWidget(self.lbl_log)
        root.addWidget(self.log_search)
        root.addWidget(self.log, 1)

        self.setCentralWidget(central)

        # Connections
        self.browse_btn.clicked.connect(self._browse)
        self.btn_start.clicked.connect(self._start)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_list.clicked.connect(self._open_dryrun_dialog)
        self.set_state("idle")
        # Enable/disable quality when audio only
        self.chk_audio.toggled.connect(self._on_audio_only_toggled)

        # Load QSS if available
        try:
            qss_path = os.path.join(os.path.dirname(__file__), "styles.qss")
            if os.path.exists(qss_path):
                with open(qss_path, "r", encoding="utf-8") as fh:
                    self.setStyleSheet(fh.read())
        except Exception:
            pass

        # Link actions
        self.btn_paste.clicked.connect(self._paste_from_clipboard)
        self.btn_detect.clicked.connect(self._detect_url)
        self.url_edit.textChanged.connect(self._detect_url_light)
        self.url_edit.textChanged.connect(lambda: self._validate_inputs(True))

        # Error actions
        self.err_hide_btn.clicked.connect(self.hide_error)
        self.err_details_btn.clicked.connect(self._show_error_details)

        # Settings then menu (order matters)
        self.settings = QSettings("yt", "allinone")
        self._load_settings()
        self._setup_menu()
        self._apply_i18n()

    def _row(self, widgets: List[QWidget]) -> QWidget:  # type: ignore[name-defined]
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        for x in widgets:
            lay.addWidget(x)
        lay.addStretch(1)
        return w

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục", self.out_edit.text() or os.getcwd())
        if d:
            self.out_edit.setText(d)
            self._validate_inputs(True)

    def _start(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        url = self.url_edit.text().strip()
        outdir = self.out_edit.text().strip()
        if not self._validate_inputs(False):
            return
        quality = self.quality_combo.currentText()
        only_audio = self.chk_audio.isChecked()
        only_shorts = self.chk_only_shorts.isChecked()
        only_regular = self.chk_only_regular.isChecked()
        limit = self.spin_limit.value()
        thumb = self.chk_thumb.isChecked()
        export_tags_flag = self.chk_tags.isChecked()
        
        # Get cookie browser selection
        cookie_browser = self.cookie_combo.currentText()
        cookies_from_browser = None if cookie_browser == "Không dùng" else cookie_browser.lower()

        # Save settings
        self._save_settings()

        self.worker = DownloadThread(url, outdir, quality, only_audio, only_shorts, only_regular, limit, thumb, export_tags_flag, cookies_from_browser)
        self.worker.signals.progress.connect(self._on_progress)
        self.worker.signals.message.connect(self._append_log)
        self.worker.signals.error.connect(self._on_error)
        self.worker.signals.done.connect(self._on_done)
        self.worker.start()
        self.set_state("running")
        self._append_log("Bắt đầu tải...")

    def _pause(self) -> None:
        if self.worker:
            if self._state == "running":
                self.worker.pause()
                self._append_log("Đã tạm dừng.")
                self.set_state("paused")
            elif self._state == "paused":
                self.worker.resume()
                self._append_log("Tiếp tục tải.")
                self.set_state("running")

    def _cancel(self) -> None:
        # Soft-cancel: cho phép tiến trình hiện tại chạy xong rồi không bắt đầu item mới
        if self.worker:
            self._append_log("Sẽ kết thúc sau khi xong video hiện tại...")
            # Không gọi terminate ngay; chỉ đặt cờ và chờ thread kết thúc vòng lặp
            try:
                self.worker.cancel()
            except Exception:
                pass
            self.set_state("paused")

    def _on_progress(self, ev: Dict[str, Any]) -> None:
        event = ev.get("event")
        if event == "progress":
            downloaded = int(ev.get("downloaded_bytes") or 0)
            total = int(ev.get("total_bytes") or 0)
            status = ev.get("status") or ""
            pct = int(ev.get("percent") or 0)
            speed = ev.get("speed") or ""
            eta = ev.get("eta") or ""
            self.update_progress_current(pct, str(speed), str(eta))
            self._append_log(f"[{status}] {downloaded}/{total} bytes")
            # overall percent if provided by thread
            if "overall_percent" in ev:
                self.update_progress_overall(int(ev["overall_percent"]), "")
        elif event == "overall":
            self.update_progress_overall(int(ev.get("overall_percent") or 0), "")

    # --- Progress helpers ---
    def update_progress_current(self, percent: int, speed: str, eta: str) -> None:
        self.item_progress.setValue(max(0, min(100, int(percent))))
        text = f"{percent}% • {speed} • ETA {eta}".strip()
        self.item_progress_label.setText(text)
        if not self.item_progress_label.isVisible():
            self.item_progress_label.setVisible(True)

    def update_progress_overall(self, percent: int, text: str) -> None:
        self.total_progress.setValue(max(0, min(100, int(percent))))
        self.total_progress_label.setText(text)
        if not self.total_progress_label.isVisible():
            self.total_progress_label.setVisible(True)

    # --- Settings persistence ---
    def _load_settings(self) -> None:
        self.url_edit.setText(self.settings.value("lastLink", "", type=str))
        out = self.settings.value("lastOutputDir", "", type=str)
        if out:
            self.out_edit.setText(out)
            if not os.path.isdir(out):
                self.out_edit.setToolTip("Thư mục không tồn tại. Hãy chọn thư mục hợp lệ.")
        q = self.settings.value("lastQuality", "best", type=str)
        idx = max(0, self.quality_combo.findText(q))
        self.quality_combo.setCurrentIndex(idx)
        cookie = self.settings.value("lastCookie", "Không dùng", type=str)
        idx = max(0, self.cookie_combo.findText(cookie))
        self.cookie_combo.setCurrentIndex(idx)
        ftype = self.settings.value("lastFilterType", "all", type=str)
        self.chk_only_shorts.setChecked(ftype == "shorts")
        self.chk_only_regular.setChecked(ftype == "regular")
        self.spin_limit.setValue(self.settings.value("lastLimit", 10, type=int))
        self.chk_thumb.setChecked(self.settings.value("optThumb", False, type=bool))
        self.chk_subs.setChecked(self.settings.value("optSubs", False, type=bool))
        self.chk_tags.setChecked(self.settings.value("optTags", False, type=bool))
        self.chk_audio.setChecked(self.settings.value("optAudioOnly", False, type=bool))
        self._sync_quality_enable()

    def _save_settings(self) -> None:
        opts = self.read_options()
        self.settings.setValue("lastLink", self.url_edit.text())
        self.settings.setValue("lastOutputDir", self.out_edit.text())
        self.settings.setValue("lastQuality", opts["quality"])
        self.settings.setValue("lastCookie", self.cookie_combo.currentText())
        self.settings.setValue("lastFilterType", opts["filterType"])
        self.settings.setValue("lastLimit", opts["limit"])
        self.settings.setValue("optThumb", opts["thumb"])
        self.settings.setValue("optSubs", opts["subtitles"])
        self.settings.setValue("optTags", opts["tags"])
        self.settings.setValue("optAudioOnly", opts["audioOnly"])

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self._save_settings()
        finally:
            super().closeEvent(event)

    def _setup_menu(self) -> None:
        mb = self.menuBar()
        view = mb.addMenu(tr("menu.view"))
        lang = view.addMenu(tr("menu.language"))
        act_vi = lang.addAction(tr("lang.vi"))
        act_en = lang.addAction(tr("lang.en"))
        act_vi.setCheckable(True)
        act_en.setCheckable(True)
        current = self.settings.value("lang", "vi", type=str)
        set_language(current)
        if current == "en":
            act_en.setChecked(True)
        else:
            act_vi.setChecked(True)

        def switch(lang_code: str) -> None:
            set_language(lang_code)
            self.settings.setValue("lang", lang_code)
            self._apply_i18n()

        act_vi.triggered.connect(lambda: switch("vi"))
        act_en.triggered.connect(lambda: switch("en"))

    def _apply_i18n(self) -> None:
        self.setWindowTitle(tr("app.title"))
        self.url_edit.setPlaceholderText(tr("link.placeholder"))
        self.browse_btn.setText(tr("btn.browse"))
        self.btn_paste.setText(tr("btn.paste"))
        self.btn_detect.setText(tr("btn.detect"))
        self.lbl_link.setText("Liên kết:")
        self.lbl_folder.setText(tr("folder"))
        self.lbl_quality.setText(tr("quality"))
        self.lbl_cookies.setText("Cookies:")
        self.lbl_filter.setText(tr("filter"))
        self.lbl_limit.setText(tr("limit"))
        self.lbl_options.setText("Tuỳ chọn:")
        self.chk_thumb.setText(tr("opt.thumb"))
        self.chk_subs.setText(tr("opt.subs"))
        self.chk_subs.setToolTip(tr("opt.subs.tt"))
        self.chk_tags.setText(tr("opt.tags"))
        self.chk_tags.setToolTip(tr("opt.tags.tt"))
        self.chk_audio.setText(tr("opt.audio"))
        self.chk_audio.setToolTip(tr("opt.audio.tt"))
        self.btn_start.setText(tr("btn.start"))
        self.btn_pause.setText(tr("btn.pause" if self._state != "paused" else "btn.resume"))
        self.btn_cancel.setText(tr("btn.stop"))
        self.btn_list.setText(tr("btn.list"))
        self.lbl_total.setText(tr("title.total"))
        self.lbl_current.setText(tr("title.current"))
        self.lbl_log.setText(tr("title.log"))
        self._validate_inputs(True)

    # --- Validation ---
    def _validate_inputs(self, quiet: bool = False) -> bool:
        ok = True
        # Reset
        self.url_edit.setProperty("error", False)
        self.out_edit.setProperty("error", False)
        self.url_edit.style().unpolish(self.url_edit)
        self.url_edit.style().polish(self.url_edit)
        self.out_edit.style().unpolish(self.out_edit)
        self.out_edit.style().polish(self.out_edit)

        url = self.url_edit.text().strip()
        folder = self.out_edit.text().strip()

        # URL regex
        import re
        url_ok = False
        patterns = [
            r"^(?:https?://)?youtu\.be/",
            r"^(?:https?://)?(?:www\.|m\.)?youtube\.com/watch",
            r"/playlist\?list=",
            r"/channel/UC",
            r"/@",
            r"/shorts/",
        ]
        if url:
            for p in patterns:
                if re.search(p, url, flags=re.I):
                    url_ok = True
                    break
            if not url_ok:
                self.url_edit.setProperty("error", True)
                self.url_edit.style().unpolish(self.url_edit)
                self.url_edit.style().polish(self.url_edit)
                if not quiet:
                    self.show_error("UNKNOWN", "Liên kết không hợp lệ.", "Kiểm tra URL YouTube hợp lệ.")
                ok = False
        else:
            # Empty URL is not an error, but Start should be disabled and error banner hidden
            url_ok = False

        # Folder exists and writable
        if not (os.path.isdir(folder) and os.access(folder, os.W_OK)):
            self.out_edit.setProperty("error", True)
            self.out_edit.style().unpolish(self.out_edit)
            self.out_edit.style().polish(self.out_edit)
            if not quiet:
                self.show_error("UNKNOWN", "Thư mục không tồn tại hoặc không ghi được.", "Chọn thư mục hợp lệ có quyền ghi.")
            ok = False

        if quiet and ok and url_ok:
            self.hide_error()

        self.btn_start.setEnabled(ok and url_ok and self._state == "idle")
        return ok

    def _on_error(self, msg: str) -> None:
        self._append_log(f"[LỖI] {msg}")
        # Try to parse 'CODE|message|hint' format defensively
        parts = [p.strip() for p in str(msg).split("|", 2)]
        if len(parts) >= 3:
            code = parts[0] if parts[0] else "UNKNOWN"
            message = parts[1] if len(parts) > 1 else str(msg)
            hint = parts[2] if len(parts) > 2 else ""
            self.show_error(code, message, hint)
        else:
            # If not in expected format, treat as unknown error
            self.show_error("UNKNOWN", str(msg), "")
        self.set_state("idle")

    def _on_done(self) -> None:
        self._append_log("Hoàn thành tải tất cả video!")
        self.item_progress.setValue(100)
        self.total_progress.setValue(100)
        self.set_state("idle")

    def _append_log(self, text: str) -> None:
        from datetime import datetime

        ts = datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText(f"{ts} {text}")

    def set_state(self, state: str) -> None:
        self._state = state
        if state == "idle":
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_cancel.setEnabled(False)
            self.btn_pause.setText("Tạm dừng")
        elif state == "running":
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_cancel.setEnabled(True)
            self.btn_pause.setText("Tạm dừng")
        elif state == "paused":
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_cancel.setEnabled(True)
            self.btn_pause.setText("Tiếp tục")
        self._sync_quality_enable()

    def _on_audio_only_toggled(self, checked: bool) -> None:
        self._sync_quality_enable()

    def _sync_quality_enable(self) -> None:
        # Disable quality selector when audio-only
        audio_only = self.chk_audio.isChecked()
        self.quality_combo.setEnabled(not audio_only)

    def read_options(self) -> dict:
        # filterType: "shorts" | "regular" | "all"
        if self.chk_only_shorts.isChecked():
            filter_type = "shorts"
        elif self.chk_only_regular.isChecked():
            filter_type = "regular"
        else:
            filter_type = "all"

        return {
            "quality": self.quality_combo.currentText(),
            "filterType": filter_type,
            "limit": int(self.spin_limit.value()),
            "thumb": self.chk_thumb.isChecked(),
            "subtitles": self.chk_subs.isChecked(),
            "tags": self.chk_tags.isChecked(),
            "audioOnly": self.chk_audio.isChecked(),
        }

    # --- Log helpers ---
    def _log_context_menu(self, pos) -> None:  # type: ignore[no-untyped-def]
        menu = QMenu(self)
        act_copy = menu.addAction("Copy")
        act_copy_all = menu.addAction("Copy All")
        act_save = menu.addAction("Save as…")
        action = menu.exec(self.log.mapToGlobal(pos))
        if action == act_copy:
            self.log.copy()
        elif action == act_copy_all:
            self.log.selectAll()
            self.log.copy()
        elif action == act_save:
            path, _ = QFileDialog.getSaveFileName(self, "Lưu nhật ký", "log.txt", "Text Files (*.txt)")
            if path:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(self.log.toPlainText())

    def _toggle_search(self) -> None:
        visible = not self.log_search.isVisible()
        self.log_search.setVisible(visible)
        if visible:
            self.log_search.setFocus()

    def _find_next(self) -> None:
        pattern = self.log_search.text().strip()
        if not pattern:
            return
        if not self.log.find(pattern):
            # wrap to top and search again
            cursor = self.log.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.log.setTextCursor(cursor)
            self.log.find(pattern)

    # --- Error banner helpers ---
    def show_error(self, code: str, message: str, hint: str) -> None:
        friendly = {
            "PRIVATE": "Video riêng tư/đã xoá.",
            "GEO_BLOCK": "Nội dung bị giới hạn khu vực.",
            "AGE_GATE": "Yêu cầu xác nhận tuổi.",
            "AUTH_REQUIRED": "YouTube yêu cầu xác thực hoặc lỗi cookies.",
            "CONTENT_UNAVAILABLE": "Nội dung không khả dụng.",
            "VIDEO_UNAVAILABLE": "Video không khả dụng.",
            "NETWORK": "Sự cố mạng hoặc máy chủ.",
            "FFMPEG_MISSING": "Thiếu ffmpeg/ffprobe.",
            "NO_SPACE": "Ổ đĩa hết dung lượng.",
            "UNKNOWN": "Lỗi không xác định.",
        }
        title = friendly.get(code, "Lỗi")
        text = f"[{code}] {title} {message}".strip()
        self.err_msg.setText(text)
        self.error_banner.setVisible(True)
        if hint:
            self._append_log(f"Gợi ý: {hint}")

    def hide_error(self) -> None:
        self.error_banner.setVisible(False)

    def _show_error_details(self) -> None:
        QMessageBox.warning(self, "Chi tiết lỗi", self.err_msg.text())

    # --- Link helpers ---
    def _paste_from_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        cb = QApplication.clipboard()
        text = cb.text() if cb else ""
        if text:
            self.url_edit.setText(text.strip())

    def _detect_url_light(self) -> None:
        url = self.url_edit.text().strip()
        kind, canonical = self.classify_url(url)
        if kind:
            self.kind_chip.setText(kind)
            self.kind_chip.setVisible(True)
        else:
            self.kind_chip.setVisible(False)

    def _detect_url(self) -> None:
        url = self.url_edit.text().strip()
        kind, canonical = self.classify_url(url)
        if kind:
            self.kind_chip.setText(kind)
            self.kind_chip.setVisible(True)
        if canonical and canonical != url:
            self.url_edit.setText(canonical)

    # Pure-UI classifier without backend
    def classify_url(self, url: str) -> tuple[str, str]:
        import re

        s = (url or "").strip()
        if not s:
            return "", ""

        video_id = r"(?P<vid>[A-Za-z0-9_-]{11})"
        list_id = r"(?P<list>[A-Za-z0-9_-]{10,})"
        channel_id = r"(?P<chid>UC[A-Za-z0-9_-]{22})"
        handle = r"(?P<handle>@[A-Za-z0-9._-]{3,30})"
        yt = r"(?:https?://)?(?:www\.|m\.)?youtube\.com"
        ytb = r"(?:https?://)?youtu\.be"

        # Bare handle
        m = re.fullmatch(handle, s)
        if m:
            h = m.group("handle").lower()
            return "HANDLE", f"https://www.youtube.com/{h}/videos"

        # youtu.be short video
        m = re.match(rf"^{ytb}/{video_id}(?:[/?#].*)?$", s, flags=re.I)
        if m:
            vid = m.group("vid")
            return "VIDEO", f"https://www.youtube.com/watch?v={vid}"

        # watch?v
        m = re.match(rf"^{yt}/watch\?(?:.*&)?v={video_id}(?:[&#/].*)?$", s, flags=re.I)
        if m:
            vid = m.group("vid")
            return "VIDEO", f"https://www.youtube.com/watch?v={vid}"

        # shorts
        m = re.match(rf"^{yt}/shorts/{video_id}(?:[/?#].*)?$", s, flags=re.I)
        if m:
            vid = m.group("vid")
            return "SHORTS", f"https://www.youtube.com/shorts/{vid}"

        # playlist
        m = re.match(rf"^{yt}/playlist\?(?:.*&)?list={list_id}(?:[&#/].*)?$", s, flags=re.I)
        if m:
            pl = m.group("list")
            return "PLAYLIST", f"https://www.youtube.com/playlist?list={pl}"

        # channel id
        m = re.match(rf"^{yt}/channel/{channel_id}(?:/.*)?$", s, flags=re.I)
        if m:
            chid = m.group("chid")
            return "CHANNEL", f"https://www.youtube.com/channel/{chid}/videos"

        # @handle url
        m = re.match(rf"^{yt}/({handle})(?:/videos)?(?:[/?#].*)?$", s, flags=re.I)
        if m:
            h = m.group("handle").lower()
            return "HANDLE", f"https://www.youtube.com/{h}/videos"

        return "", s

    # --- Dry-run dialog ---
    def _open_dryrun_dialog(self) -> None:
        demo = [
            {"title": "Video A", "duration": 180, "type": "Video", "url": "https://youtu.be/aaaa"},
            {"title": "Shorts B", "duration": 45, "type": "Shorts", "url": "https://youtube.com/shorts/bbbb"},
            {"title": "Video C", "duration": 620, "type": "Video", "url": "https://youtu.be/cccc"},
            {"title": "Shorts D", "duration": 58, "type": "Shorts", "url": "https://youtube.com/shorts/dddd"},
            {"title": "Video E", "duration": 210, "type": "Video", "url": "https://youtu.be/eeee"},
        ]
        dlg = DryRunDialog(self, demo)
        dlg.exec()


class DryRunDialog(QDialog):
    def __init__(self, parent: QWidget | None, rows: list[dict]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Liệt kê (Dry-run)")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Filters
        filter_bar = QHBoxLayout()
        filter_bar.setContentsMargins(12, 12, 12, 12)
        filter_bar.setSpacing(8)
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["All", "Regular", "Shorts"])
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Tìm tiêu đề...")
        filter_bar.addWidget(QLabel("Lọc:"))
        filter_bar.addWidget(self.cmb_type)
        filter_bar.addWidget(self.search_edit, 1)
        layout.addLayout(filter_bar)

        # Table
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        from PySide6.QtCore import QSortFilterProxyModel

        self.model = QStandardItemModel(0, 5, self)
        self.model.setHorizontalHeaderLabels(["#", "Tiêu đề", "Thời lượng", "Loại", "URL"])
        for idx, r in enumerate(rows, 1):
            items = [
                QStandardItem(str(idx)),
                QStandardItem(str(r.get("title", ""))),
                QStandardItem(str(r.get("duration", ""))),
                QStandardItem(str(r.get("type", ""))),
                QStandardItem(str(r.get("url", ""))),
            ]
            self.model.appendRow(items)

        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(1)  # title
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.table = QTableView(self)
        self.table.setModel(self.proxy)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        # Buttons
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(12, 12, 12, 12)
        btn_bar.setSpacing(8)
        self.btn_csv = QPushButton("Xuất CSV")
        self.btn_json = QPushButton("Xuất JSON")
        self.btn_close = QPushButton("Đóng")
        btn_bar.addWidget(self.btn_csv)
        btn_bar.addWidget(self.btn_json)
        btn_bar.addStretch(1)
        btn_bar.addWidget(self.btn_close)
        layout.addLayout(btn_bar)

        # Wire
        self.search_edit.textChanged.connect(self.proxy.setFilterFixedString)
        self.cmb_type.currentTextChanged.connect(self._apply_type_filter)
        self.btn_close.clicked.connect(self.accept)
        self.btn_csv.clicked.connect(self._export_csv)
        self.btn_json.clicked.connect(self._export_json)

    def _apply_type_filter(self, text: str) -> None:
        from PySide6.QtCore import QRegularExpression

        if text == "All":
            self.proxy.setFilterRegularExpression(QRegularExpression(self.search_edit.text(), QRegularExpression.CaseInsensitiveOption))
            self.proxy.setFilterKeyColumn(1)
            return
        # Filter by type via a second proxy or simple manual filter: change filter column to type
        self.proxy.setFilterKeyColumn(3)  # type column
        self.proxy.setFilterFixedString("Shorts" if text == "Shorts" else "Video")

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Lưu CSV", "dryrun.csv", "CSV Files (*.csv)")
        if not path:
            return
        import csv

        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["#", "title", "duration", "type", "url"])
            for r in range(self.proxy.rowCount()):
                row = [self.proxy.index(r, c).data() for c in range(5)]
                writer.writerow(row)

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Lưu JSON", "dryrun.json", "JSON Files (*.json)")
        if not path:
            return
        import json

        rows = []
        for r in range(self.proxy.rowCount()):
            rows.append({
                "index": self.proxy.index(r, 0).data(),
                "title": self.proxy.index(r, 1).data(),
                "duration": self.proxy.index(r, 2).data(),
                "type": self.proxy.index(r, 3).data(),
                "url": self.proxy.index(r, 4).data(),
            })
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=2)

    # --- Link helpers ---
    def _paste_from_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        cb = QApplication.clipboard()
        text = cb.text() if cb else ""
        if text:
            self.url_edit.setText(text.strip())

    def _detect_url_light(self) -> None:
        url = self.url_edit.text().strip()
        kind, canonical = self.classify_url(url)
        if kind:
            self.kind_chip.setText(kind)
            self.kind_chip.setVisible(True)
        else:
            self.kind_chip.setVisible(False)

    def _detect_url(self) -> None:
        url = self.url_edit.text().strip()
        kind, canonical = self.classify_url(url)
        if kind:
            self.kind_chip.setText(kind)
            self.kind_chip.setVisible(True)
        if canonical and canonical != url:
            self.url_edit.setText(canonical)

    # Pure-UI classifier without backend
    def classify_url(self, url: str) -> tuple[str, str]:
        import re

        s = (url or "").strip()
        if not s:
            return "", ""

        video_id = r"(?P<vid>[A-Za-z0-9_-]{11})"
        list_id = r"(?P<list>[A-Za-z0-9_-]{10,})"
        channel_id = r"(?P<chid>UC[A-Za-z0-9_-]{22})"
        handle = r"(?P<handle>@[A-Za-z0-9._-]{3,30})"
        yt = r"(?:https?://)?(?:www\.|m\.)?youtube\.com"
        ytb = r"(?:https?://)?youtu\.be"

        # Bare handle
        m = re.fullmatch(handle, s)
        if m:
            h = m.group("handle").lower()
            return "HANDLE", f"https://www.youtube.com/{h}/videos"

        # youtu.be short video
        m = re.match(rf"^{ytb}/{video_id}(?:[/?#].*)?$", s, flags=re.I)
        if m:
            vid = m.group("vid")
            return "VIDEO", f"https://www.youtube.com/watch?v={vid}"

        # watch?v
        m = re.match(rf"^{yt}/watch\?(?:.*&)?v={video_id}(?:[&#/].*)?$", s, flags=re.I)
        if m:
            vid = m.group("vid")
            return "VIDEO", f"https://www.youtube.com/watch?v={vid}"

        # shorts
        m = re.match(rf"^{yt}/shorts/{video_id}(?:[/?#].*)?$", s, flags=re.I)
        if m:
            vid = m.group("vid")
            return "SHORTS", f"https://www.youtube.com/shorts/{vid}"

        # playlist
        m = re.match(rf"^{yt}/playlist\?(?:.*&)?list={list_id}(?:[&#/].*)?$", s, flags=re.I)
        if m:
            pl = m.group("list")
            return "PLAYLIST", f"https://www.youtube.com/playlist?list={pl}"

        # channel id
        m = re.match(rf"^{yt}/channel/{channel_id}(?:/.*)?$", s, flags=re.I)
        if m:
            chid = m.group("chid")
            return "CHANNEL", f"https://www.youtube.com/channel/{chid}/videos"

        # @handle url
        m = re.match(rf"^{yt}/({handle})(?:/videos)?(?:[/?#].*)?$", s, flags=re.I)
        if m:
            h = m.group("handle").lower()
            return "HANDLE", f"https://www.youtube.com/{h}/videos"

        return "", s

