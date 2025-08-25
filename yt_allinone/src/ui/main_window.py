from __future__ import annotations

import os
from typing import Optional, Callable, List, Dict, Any

from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtGui import QIcon, QTextCursor
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
    QTextEdit,
    QGroupBox,
    QFormLayout,
)

from yt_allinone.src.core.selector import build_format_selector
from yt_allinone.src.core.filters import is_shorts, is_regular
from yt_allinone.src.core.exporter import download_best_thumbnail, export_tags
from yt_allinone.src.core.models import DownloadTask
from yt_allinone.src.download.ytdlp_wrapper import YtDlpWrapper
from yt_allinone.src.download.queue import DownloadManager
from yt_allinone.src.utils.config import get_default_download_dir


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

            entries = wrapper.dry_run(self.url, filter_fn=filter_fn, limit=self.limit)
            if self.thumb:
                os.makedirs(self.outdir, exist_ok=True)
                for e in entries:
                    path = download_best_thumbnail(e.id, e.raw.get("thumbnails") if e.raw else None)
                    if path:
                        dest = os.path.join(self.outdir, f"{e.id}.jpg")
                        try:
                            os.replace(path, dest)
                        except Exception:
                            pass

            for e in entries:
                fmt = build_format_selector(self.quality)
                task = DownloadTask(url=e.url or e.webpage_url or f"https://www.youtube.com/watch?v={e.id}", outdir=self.outdir, quality=self.quality, only_audio=self.only_audio, options={"format": fmt})
                self.signals.message.emit(f"Đang tải: {task.url}")
                self.manager.start(task)
                if self.manager._proc:  # noqa: SLF001
                    self.manager._proc.wait()

            if self.export_tags_flag:
                export_tags((e.raw or {"id": e.id, "title": e.title, "tags": e.raw.get("tags") if e.raw else []} for e in entries), self.outdir)

            self.signals.done.emit()
        except Exception as exc:  # pragma: no cover
            self.signals.error.emit(str(exc))

    def pause(self) -> None:
        self.manager.pause()

    def resume(self) -> None:
        self.manager.resume()

    def cancel(self) -> None:
        self.manager.cancel(delete_part=False)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("yt-allinone")
        try:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "assets", "icon.png")
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        self.worker: Optional[DownloadThread] = None

        central = QWidget(self)
        root = QVBoxLayout(central)

        # Input group
        input_group = QGroupBox("Nguồn")
        form = QFormLayout(input_group)
        self.url_edit = QLineEdit()
        self.out_edit = QLineEdit(get_default_download_dir())
        self.browse_btn = QPushButton("Chọn...")
        out_layout = QHBoxLayout()
        out_container = QWidget()
        out_layout.setContentsMargins(0, 0, 0, 0)
        out_layout.addWidget(self.out_edit)
        out_layout.addWidget(self.browse_btn)
        out_container.setLayout(out_layout)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["best", "1080p", "720p", "480p"])
        self.chk_only_shorts = QCheckBox("Chỉ Shorts")
        self.chk_only_regular = QCheckBox("Chỉ video thường")
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 10000)
        self.spin_limit.setValue(10)
        self.chk_thumb = QCheckBox("Tải thumbnail")
        self.chk_subs = QCheckBox("Tải phụ đề/Không tải video")
        self.chk_tags = QCheckBox("Tải thẻ Tag (export tags)")
        self.chk_audio = QCheckBox("Chỉ tải MP3")

        form.addRow("Liên kết:", self.url_edit)
        form.addRow("Thư mục:", out_container)
        form.addRow("Chất lượng:", self.quality_combo)
        form.addRow("Lọc:", self._row([self.chk_only_shorts, self.chk_only_regular]))
        form.addRow("Giới hạn:", self.spin_limit)
        form.addRow("Tuỳ chọn:", self._row([self.chk_thumb, self.chk_subs, self.chk_tags, self.chk_audio]))

        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_start = QPushButton("Bắt đầu")
        self.btn_pause = QPushButton("Tạm dừng")
        self.btn_cancel = QPushButton("Kết thúc")
        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addWidget(self.btn_pause)
        ctrl_layout.addWidget(self.btn_cancel)

        # Progress and log
        self.total_progress = QProgressBar()
        self.total_progress.setRange(0, 100)
        self.item_progress = QProgressBar()
        self.item_progress.setRange(0, 100)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)

        root.addWidget(input_group)
        root.addLayout(ctrl_layout)
        root.addWidget(QLabel("Tiến độ tổng:"))
        root.addWidget(self.total_progress)
        root.addWidget(QLabel("Tiến độ hiện tại:"))
        root.addWidget(self.item_progress)
        root.addWidget(QLabel("Nhật ký:"))
        root.addWidget(self.log, 1)

        self.setCentralWidget(central)

        # Connections
        self.browse_btn.clicked.connect(self._browse)
        self.btn_start.clicked.connect(self._start)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_cancel.clicked.connect(self._cancel)
        self._update_buttons(idle=True)

    def _row(self, widgets: List[QWidget]) -> QWidget:  # type: ignore[name-defined]
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        for x in widgets:
            lay.addWidget(x)
        lay.addStretch(1)
        return w

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục", self.out_edit.text() or os.getcwd())
        if d:
            self.out_edit.setText(d)

    def _start(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        url = self.url_edit.text().strip()
        outdir = self.out_edit.text().strip() or os.path.join(os.getcwd(), "downloads")
        quality = self.quality_combo.currentText()
        only_audio = self.chk_audio.isChecked()
        only_shorts = self.chk_only_shorts.isChecked()
        only_regular = self.chk_only_regular.isChecked()
        limit = self.spin_limit.value()
        thumb = self.chk_thumb.isChecked()
        export_tags_flag = self.chk_tags.isChecked()
        cookies_from_browser = None

        self.worker = DownloadThread(url, outdir, quality, only_audio, only_shorts, only_regular, limit, thumb, export_tags_flag, cookies_from_browser)
        self.worker.signals.progress.connect(self._on_progress)
        self.worker.signals.message.connect(self._append_log)
        self.worker.signals.error.connect(self._on_error)
        self.worker.signals.done.connect(self._on_done)
        self.worker.start()
        self._update_buttons(idle=False)
        self._append_log("Bắt đầu tải...")

    def _pause(self) -> None:
        if self.worker:
            self.worker.pause()
            self._append_log("Đã tạm dừng.")

    def _cancel(self) -> None:
        if self.worker:
            self.worker.cancel()
            self._append_log("Đã huỷ tác vụ.")
            self._update_buttons(idle=True)

    def _on_progress(self, ev: Dict[str, Any]) -> None:
        if ev.get("event") != "progress":
            return
        downloaded = int(ev.get("downloaded_bytes") or 0)
        total = int(ev.get("total_bytes") or 0)
        status = ev.get("status") or ""
        if total > 0:
            pct = int(downloaded * 100 / max(1, total))
            self.item_progress.setValue(pct)
        self._append_log(f"[{status}] {downloaded}/{total} bytes")

    def _on_error(self, msg: str) -> None:
        self._append_log(f"Lỗi: {msg}")
        self._update_buttons(idle=True)

    def _on_done(self) -> None:
        self._append_log("Hoàn tất!")
        self.item_progress.setValue(100)
        self.total_progress.setValue(100)
        self._update_buttons(idle=True)

    def _append_log(self, text: str) -> None:
        self.log.append(text)
        try:
            self.log.moveCursor(QTextCursor.MoveOperation.End)
        except Exception:
            pass

    def _update_buttons(self, idle: bool) -> None:
        self.btn_start.setEnabled(idle)
        self.btn_pause.setEnabled(not idle)
        self.btn_cancel.setEnabled(not idle)

