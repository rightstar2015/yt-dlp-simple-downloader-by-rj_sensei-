"""yt-dlp GUI 1.1: responsive interface with cancellable background tasks."""
from datetime import datetime
from pathlib import Path
import sys

from PyQt5 import QtCore, QtGui, QtWidgets
import downloader_core as core
from downloader_workers import TaskWorker
from style import QSS_STYLE


class YtDlpGui(QtWidgets.QWidget):
    def __init__(self, auto_check=True):
        super().__init__()
        core.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.settings = QtCore.QSettings(str(core.APP_DATA_DIR / "settings.ini"), QtCore.QSettings.IniFormat)
        self._worker = None
        self._closing = False
        self._cache = {}
        self._info_url = ""
        self._pending_probe = False
        self._last_files = []
        self._queue_running = False
        self._queue_successes = 0
        self._queue_failures = 0
        self.setWindowTitle(f"yt-dlp GUI Downloader {core.VERSION}")
        self.setStyleSheet(QSS_STYLE + """
            QPlainTextEdit, QListWidget {background: #1e293b; border: 1px solid #334155;
                border-radius: 6px; padding: 6px;}
        """)
        self.setMinimumSize(650, 540)
        self.resize(900, 820)
        self.init_ui()
        self.restore_settings()
        self.url_input.textChanged.connect(self.url_changed)
        for widget in (self.fmt_combo, self.video_combo, self.audio_combo):
            widget.currentIndexChanged.connect(self.update_estimate)
        for widget in (self.start_input, self.end_input):
            widget.textChanged.connect(self.update_estimate)
        self.clip_radio.toggled.connect(self.update_estimate)
        self.playlist_checkbox.toggled.connect(self.update_estimate)
        if auto_check:
            QtCore.QTimer.singleShot(0, self.update_dependencies_status)

    def init_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        outer.addWidget(scroll)
        body = QtWidgets.QWidget()
        scroll.setWidget(body)
        layout = QtWidgets.QVBoxLayout(body)
        layout.setSpacing(10)

        self.tools_status = QtWidgets.QLabel("工具狀態：等候背景檢查...")
        self.tools_status.setWordWrap(True)
        layout.addWidget(self.tools_status)
        layout.addWidget(QtWidgets.QLabel("影片網址（支援 yt-dlp 可下載的網站）："))
        self.url_input = QtWidgets.QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        layout.addWidget(self.url_input)
        self.playlist_checkbox = QtWidgets.QCheckBox("下載播放清單（簡單模式；未勾選時最多下載單支影片）")
        layout.addWidget(self.playlist_checkbox)

        path_row = QtWidgets.QHBoxLayout()
        path_row.addWidget(QtWidgets.QLabel("下載位置："))
        self.path_input = QtWidgets.QLineEdit()
        self.path_btn = QtWidgets.QPushButton("選擇資料夾")
        self.path_btn.clicked.connect(self.choose_folder)
        path_row.addWidget(self.path_input, 1)
        path_row.addWidget(self.path_btn)
        layout.addLayout(path_row)
        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(QtWidgets.QLabel("檔案名稱："))
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("可留空；播放清單與分開下載會自動加上識別碼")
        name_row.addWidget(self.name_input)
        layout.addLayout(name_row)

        self.mode_group = QtWidgets.QGroupBox("下載範圍")
        range_layout = QtWidgets.QVBoxLayout(self.mode_group)
        range_row = QtWidgets.QHBoxLayout()
        self.full_radio = QtWidgets.QRadioButton("全片下載")
        self.clip_radio = QtWidgets.QRadioButton("指定時間下載")
        self.full_radio.setChecked(True)
        range_row.addWidget(self.full_radio)
        range_row.addWidget(self.clip_radio)
        range_layout.addLayout(range_row)
        self.time_group = QtWidgets.QWidget()
        time_layout = QtWidgets.QHBoxLayout(self.time_group)
        time_layout.setContentsMargins(0, 0, 0, 0)
        self.start_input = QtWidgets.QLineEdit()
        self.start_input.setPlaceholderText("00:00:00")
        self.end_input = QtWidgets.QLineEdit()
        self.end_input.setPlaceholderText("留空則到影片結尾")
        time_layout.addWidget(QtWidgets.QLabel("開始："))
        time_layout.addWidget(self.start_input)
        time_layout.addWidget(QtWidgets.QLabel("結束："))
        time_layout.addWidget(self.end_input)
        range_layout.addWidget(self.time_group)
        layout.addWidget(self.mode_group)
        self.clip_radio.toggled.connect(self.toggle_time_group)

        mode_row = QtWidgets.QHBoxLayout()
        self.mode_group_btn = QtWidgets.QButtonGroup(self)
        self.simple_mode_radio = QtWidgets.QRadioButton("簡單模式")
        self.advanced_mode_radio = QtWidgets.QRadioButton("進階模式")
        self.simple_mode_radio.setChecked(True)
        for radio in (self.simple_mode_radio, self.advanced_mode_radio):
            self.mode_group_btn.addButton(radio)
            mode_row.addWidget(radio)
        mode_row.addStretch()
        self.fmt_refresh_btn = QtWidgets.QPushButton("取得影片資訊／格式")
        self.fmt_refresh_btn.clicked.connect(self.fetch_formats)
        mode_row.addWidget(self.fmt_refresh_btn)
        layout.addLayout(mode_row)
        self.simple_panel = QtWidgets.QWidget()
        simple_row = QtWidgets.QHBoxLayout(self.simple_panel)
        simple_row.setContentsMargins(0, 0, 0, 0)
        simple_row.addWidget(QtWidgets.QLabel("下載格式："))
        self.fmt_combo = QtWidgets.QComboBox()
        self.fmt_combo.addItems(["mp4", "mp3", "m4a"])
        simple_row.addWidget(self.fmt_combo)
        format_hint = QtWidgets.QLabel("MP4 使用 H.264／AAC；音訊轉檔需 FFmpeg。")
        format_hint.setWordWrap(True)
        simple_row.addWidget(format_hint, 1)
        layout.addWidget(self.simple_panel)
        self.advanced_fmt_group = QtWidgets.QGroupBox("進階格式")
        advanced_layout = QtWidgets.QFormLayout(self.advanced_fmt_group)
        self.video_combo = QtWidgets.QComboBox()
        self.audio_combo = QtWidgets.QComboBox()
        self.video_combo.addItem("不下載影片", "")
        self.audio_combo.addItem("不下載音訊", "")
        for combo in (self.video_combo, self.audio_combo):
            combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(20)
        advanced_layout.addRow("影片：", self.video_combo)
        advanced_layout.addRow("音訊：", self.audio_combo)
        self.merge_checkbox = QtWidgets.QCheckBox("合併影音；取消勾選則輸出各自的檔案")
        self.merge_checkbox.setChecked(True)
        advanced_layout.addRow(self.merge_checkbox)
        layout.addWidget(self.advanced_fmt_group)
        self.simple_mode_radio.toggled.connect(self.toggle_mode)
        self.advanced_mode_radio.toggled.connect(self.toggle_mode)
        self.estimate_label = QtWidgets.QLabel("大小待取得影片資訊")
        self.estimate_label.setWordWrap(True)
        layout.addWidget(self.estimate_label)

        action_row = QtWidgets.QHBoxLayout()
        self.download_btn = QtWidgets.QPushButton("下載影片")
        self.download_btn.setObjectName("download_btn")
        self.download_btn.clicked.connect(self.download_video)
        self.cancel_btn = QtWidgets.QPushButton("取消工作")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_task)
        self.add_queue_btn = QtWidgets.QPushButton("加入佇列")
        self.add_queue_btn.clicked.connect(self.add_to_queue)
        for button in (self.download_btn, self.add_queue_btn, self.cancel_btn):
            action_row.addWidget(button)
        layout.addLayout(action_row)
        self.queue_label = QtWidgets.QLabel("下載佇列：0 項")
        layout.addWidget(self.queue_label)
        self.queue_list = QtWidgets.QListWidget()
        self.queue_list.setMaximumHeight(120)
        self.queue_list.setToolTip("佇列保存加入時的網址、格式與下載位置")
        self.queue_list.setVisible(False)
        layout.addWidget(self.queue_list)
        queue_row = QtWidgets.QHBoxLayout()
        self.run_queue_btn = QtWidgets.QPushButton("開始佇列")
        self.run_queue_btn.clicked.connect(self.start_queue)
        self.remove_queue_btn = QtWidgets.QPushButton("移除選取項目")
        self.remove_queue_btn.clicked.connect(self.remove_from_queue)
        queue_row.addWidget(self.run_queue_btn)
        queue_row.addWidget(self.remove_queue_btn)
        queue_row.addStretch()
        layout.addLayout(queue_row)

        tool_row = QtWidgets.QHBoxLayout()
        self.update_btn = QtWidgets.QPushButton("更新 yt-dlp")
        self.update_btn.clicked.connect(self.update_ytdlp)
        self.update_ffmpeg_btn = QtWidgets.QPushButton("安裝／更新 FFmpeg")
        self.update_ffmpeg_btn.clicked.connect(self.download_ffmpeg)
        self.check_btn = QtWidgets.QPushButton("檢查工具")
        self.check_btn.clicked.connect(self.update_dependencies_status)
        for button in (self.update_btn, self.update_ffmpeg_btn, self.check_btn):
            tool_row.addWidget(button)
        layout.addLayout(tool_row)
        ffmpeg_row = QtWidgets.QHBoxLayout()
        ffmpeg_row.addWidget(QtWidgets.QLabel("FFmpeg 資料夾："))
        self.ffmpeg_input = QtWidgets.QLineEdit()
        self.ffmpeg_input.setPlaceholderText("留空則自動尋找本機工具或系統 PATH")
        self.ffmpeg_btn = QtWidgets.QPushButton("選擇")
        self.ffmpeg_btn.clicked.connect(self.choose_ffmpeg)
        ffmpeg_row.addWidget(self.ffmpeg_input, 1)
        ffmpeg_row.addWidget(self.ffmpeg_btn)
        layout.addLayout(ffmpeg_row)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        outer.addWidget(self.progress_bar)
        self.eta_label = QtWidgets.QLabel("")
        self.eta_label.setVisible(False)
        self.eta_label.setWordWrap(True)
        outer.addWidget(self.eta_label)
        self.status = QtWidgets.QLabel("就緒")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        open_row = QtWidgets.QHBoxLayout()
        self.open_file_btn = QtWidgets.QPushButton("開啟完成檔案")
        self.open_file_btn.setEnabled(False)
        self.open_file_btn.clicked.connect(self.open_last_file)
        self.open_folder_btn = QtWidgets.QPushButton("開啟下載資料夾")
        self.open_folder_btn.clicked.connect(self.open_folder)
        open_row.addWidget(self.open_file_btn)
        open_row.addWidget(self.open_folder_btn)
        open_row.addStretch()
        layout.addLayout(open_row)
        log_row = QtWidgets.QHBoxLayout()
        self.log_checkbox = QtWidgets.QCheckBox("顯示工作紀錄")
        self.log_checkbox.toggled.connect(lambda visible: self.log_box.setVisible(visible))
        self.copy_log_btn = QtWidgets.QPushButton("複製紀錄")
        self.copy_log_btn.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(self.log_box.toPlainText()))
        self.save_log_btn = QtWidgets.QPushButton("儲存紀錄")
        self.save_log_btn.clicked.connect(self.save_log)
        log_row.addWidget(self.log_checkbox)
        log_row.addStretch()
        log_row.addWidget(self.copy_log_btn)
        log_row.addWidget(self.save_log_btn)
        layout.addLayout(log_row)
        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(2000)
        self.log_box.setMinimumHeight(150)
        self.log_box.setVisible(False)
        layout.addWidget(self.log_box)
        self.note = QtWidgets.QLabel(f"工具儲存位置：{core.APP_DATA_DIR}\n問題回報：X / Twitter @rj_sensei_")
        self.note.setObjectName("note")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        layout.addStretch()
        self.toggle_time_group()
        self.toggle_mode()
        self.refresh_queue()

    def restore_settings(self):
        default_folder = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DownloadLocation)
        if not Path(default_folder).is_dir():
            default_folder = str(Path.home())
        self.path_input.setText(self.settings.value("folder", default_folder, type=str))
        self.ffmpeg_input.setText(self.settings.value("ffmpeg_dir", "", type=str))
        self.fmt_combo.setCurrentText(self.settings.value("format", "mp4", type=str))
        self.advanced_mode_radio.setChecked(self.settings.value("advanced", False, type=bool))
        self.merge_checkbox.setChecked(self.settings.value("merge", True, type=bool))
        self.playlist_checkbox.setChecked(self.settings.value("playlist", False, type=bool))
        self.log_checkbox.setChecked(self.settings.value("show_log", False, type=bool))
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.toggle_mode()

    def save_settings(self):
        for name, value in (("folder", self.path_input.text()), ("ffmpeg_dir", self.ffmpeg_input.text()),
                            ("format", self.fmt_combo.currentText()), ("advanced", self.advanced_mode_radio.isChecked()),
                            ("merge", self.merge_checkbox.isChecked()), ("playlist", self.playlist_checkbox.isChecked()),
                            ("show_log", self.log_checkbox.isChecked()), ("geometry", self.saveGeometry())):
            self.settings.setValue(name, value)
        self.settings.sync()

    def toggle_time_group(self):
        self.time_group.setEnabled(self.clip_radio.isChecked())

    def toggle_mode(self):
        simple = self.simple_mode_radio.isChecked()
        self.simple_panel.setVisible(simple)
        self.advanced_fmt_group.setVisible(not simple)
        self.update_estimate()

    def choose_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "選擇下載資料夾", self.path_input.text())
        if folder:
            self.path_input.setText(folder)

    def choose_ffmpeg(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "選擇含 ffmpeg.exe 與 ffprobe.exe 的資料夾")
        if folder:
            self.ffmpeg_input.setText(folder)
            self.update_dependencies_status()

    def current_request(self):
        return core.DownloadRequest(url=self.url_input.text().strip(), folder=self.path_input.text().strip(),
                                    name=self.name_input.text(), mode=self.fmt_combo.currentText() if self.simple_mode_radio.isChecked() else "advanced",
                                    video_id=self.video_combo.currentData() or "", audio_id=self.audio_combo.currentData() or "",
                                    merge=self.merge_checkbox.isChecked(), playlist=self.playlist_checkbox.isChecked(),
                                    clip=self.clip_radio.isChecked(), start=self.start_input.text().strip(),
                                    end=self.end_input.text().strip(), ffmpeg_dir=self.ffmpeg_input.text().strip())

    def url_changed(self):
        url = self.url_input.text().strip()
        if url in self._cache:
            self.populate_formats(url, self._cache[url])
        elif self._info_url:
            self._info_url = ""
            for combo, label in ((self.video_combo, "不下載影片"), (self.audio_combo, "不下載音訊")):
                combo.clear()
                combo.addItem(label, "")
        self.update_estimate()

    def populate_formats(self, url, info):
        self._info_url = url
        video, audio = core.available_formats(info)
        for combo, items, placeholder in ((self.video_combo, video, "不下載影片"),
                                           (self.audio_combo, audio, "不下載音訊")):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(placeholder, "")
            for item in items:
                fid = str(item["format_id"])
                resolution = f"{item.get('height')}p" if item.get("height") else "音訊"
                codec = (item.get("vcodec") if combo is self.video_combo else item.get("acodec")) or "編碼未知"
                size = core.format_size(item.get("filesize") or item.get("filesize_approx"))
                combined = "（含音訊）" if combo is self.video_combo and item.get("acodec") not in (None, "none") else ""
                combo.addItem(f"{resolution} | {item.get('ext', '')} | {codec} | {size} | ID {fid} {combined}", fid)
            combo.blockSignals(False)
        self.update_estimate()

    def update_estimate(self):
        if not hasattr(self, "estimate_label"):
            return
        request = self.current_request()
        self.estimate_label.setText(core.estimate_size(request, self._cache.get(request.url)))

    def set_status(self, message, state="busy"):
        colors = {"busy": "#60a5fa", "success": "#10b981", "error": "#f87171", "cancelled": "#fbbf24"}
        self.status.setStyleSheet(f"color: {colors.get(state, '#e2e8f0')}; font-weight: bold;")
        self.status.setText(message.splitlines()[0] if message else "就緒")

    @QtCore.pyqtSlot(str)
    def append_log(self, message):
        self.log_box.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def _set_busy(self, busy):
        for button in (self.download_btn, self.update_btn, self.update_ffmpeg_btn, self.check_btn,
                       self.fmt_refresh_btn, self.ffmpeg_btn, self.add_queue_btn, self.run_queue_btn,
                       self.remove_queue_btn):
            button.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)
        self.progress_bar.setVisible(busy)
        self.eta_label.setVisible(busy)
        if busy:
            self.progress_bar.setRange(0, 0)
            self.eta_label.setText("正在處理...")
        else:
            self.progress_bar.setRange(0, 100)
            self.refresh_queue()

    def start_task(self, operation, params=None):
        if self._worker is not None or self._closing:
            return False
        self.save_settings()
        self._set_busy(True)
        self._worker = TaskWorker(operation, params, self)
        self._worker.status_changed.connect(self._status_changed)
        self._worker.progress_changed.connect(self._progress_changed)
        self._worker.log_message.connect(self.append_log)
        self._worker.result_ready.connect(self._task_result)
        self._worker.finished.connect(self._task_finished)
        self.append_log(f"開始工作：{operation}")
        self._worker.start()
        return True

    def update_dependencies_status(self):
        self.start_task("probe", {"ffmpeg_dir": self.ffmpeg_input.text().strip(),
                                  "latest": self.settings.value("latest", "", type=str),
                                  "checked": self.settings.value("checked", 0, type=float)})

    def fetch_formats(self):
        try:
            url = core.validate_url(self.url_input.text())
            if self.playlist_checkbox.isChecked():
                raise ValueError("格式清單與大小估算只支援單片；播放清單請使用簡單模式。")
            self.start_task("info", {"url": url, "ffmpeg_dir": self.ffmpeg_input.text().strip()})
        except ValueError as error:
            self.set_status(str(error), "error")

    def _validated_request(self):
        request = self.current_request()
        info = self._cache.get(request.url)
        core.validate_request(request, info)
        if request.mode == "advanced" and self._info_url != request.url:
            raise ValueError("網址已變更，請先重新取得格式清單。")
        return request, info

    def download_video(self):
        try:
            request, info = self._validated_request()
            self.start_task("download", {"request": request, "info": info})
        except ValueError as error:
            self.set_status(str(error), "error")

    def update_ytdlp(self):
        self.start_task("update")

    def download_ffmpeg(self):
        self.start_task("ffmpeg")

    def cancel_task(self):
        self._queue_running = False
        if self._worker:
            self._worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.set_status("正在取消，完成清理後會恢復操作...", "cancelled")

    @QtCore.pyqtSlot(str)
    def _status_changed(self, message):
        if not self._closing and self._worker and not self._worker.cancel_event.is_set():
            self.set_status(message)

    @QtCore.pyqtSlot(int, str)
    def _progress_changed(self, percent, message):
        if self._closing:
            return
        self.progress_bar.setRange(0, 0 if percent < 0 else 100)
        if percent >= 0:
            self.progress_bar.setValue(percent)
        self.eta_label.setText(message)

    @QtCore.pyqtSlot(bool, object, str)
    def _task_result(self, success, data, message):
        operation = self._worker.operation
        self.append_log(message)
        self.set_status(message, "success" if success else "cancelled" if data.get("cancelled") else "error")
        if not success:
            self.log_checkbox.setChecked(True)
        if operation == "probe" and success:
            tools = data["tools"]
            versions = data["versions"]
            local = versions.get("yt-dlp", "未安裝或無法執行")
            latest = data.get("latest", "")
            latest_note = f" | 最新：{latest}" if latest else ""
            ffmpeg = "已驗證" if tools.get("ffmpeg") and tools.get("ffprobe") else "未安裝或驗證失敗"
            self.tools_status.setText(f"yt-dlp：{local}{latest_note} | FFmpeg／FFprobe：{ffmpeg}")
            for name in ("latest", "checked"):
                self.settings.setValue(name, data.get(name, "" if name == "latest" else 0))
            for name, path in tools.items():
                if path:
                    self.append_log(f"{name}：{path}")
        elif operation == "info" and success:
            if len(self._cache) >= 20:
                self._cache.pop(next(iter(self._cache)))
            self._cache[data["url"]] = data["info"]
            if self.url_input.text().strip() == data["url"]:
                self.populate_formats(data["url"], data["info"])
        elif operation in ("update", "ffmpeg") and success:
            self._pending_probe = True
            if operation == "update":
                self._cache.clear()
                self.url_changed()
            else:
                self.ffmpeg_input.clear()
                self.append_log("已切換使用應用程式工具資料夾中的新 FFmpeg／FFprobe。")
        if data.get("files"):
            self._last_files = data["files"]
            self.open_file_btn.setEnabled(True)
        if operation == "download" and self._queue_running:
            if success:
                self._queue_successes += 1
            else:
                self._queue_failures += 1

    @QtCore.pyqtSlot()
    def _task_finished(self):
        worker = self._worker
        self._worker = None
        worker.deleteLater()
        self._set_busy(False)
        if self._closing:
            self.close()
        elif self._queue_running:
            self._next_queued_download()
        elif self._pending_probe:
            self._pending_probe = False
            QtCore.QTimer.singleShot(0, self.update_dependencies_status)

    def add_to_queue(self):
        try:
            request, info = self._validated_request()
            item = QtWidgets.QListWidgetItem(f"{request.mode.upper()} | {request.url}")
            item.setData(QtCore.Qt.UserRole, (request, info))
            self.queue_list.addItem(item)
            self.refresh_queue()
            self.set_status(f"已加入佇列，共 {self.queue_list.count()} 項。", "success")
        except ValueError as error:
            self.set_status(str(error), "error")

    def remove_from_queue(self):
        for item in self.queue_list.selectedItems():
            self.queue_list.takeItem(self.queue_list.row(item))
        self.refresh_queue()

    def refresh_queue(self):
        count = self.queue_list.count()
        self.queue_label.setText(f"下載佇列：{count} 項")
        self.queue_list.setVisible(count > 0)
        if self._worker is None:
            self.run_queue_btn.setEnabled(count > 0)
            self.remove_queue_btn.setEnabled(count > 0)

    def start_queue(self):
        if self._worker is not None:
            return
        if not self.queue_list.count():
            self.set_status("佇列是空的，請先加入影片。", "error")
            return
        self._queue_running = True
        self._queue_successes = self._queue_failures = 0
        self._next_queued_download()

    def _next_queued_download(self):
        if not self.queue_list.count():
            self._queue_running = False
            self.set_status(f"佇列完成：成功 {self._queue_successes} 項，失敗 {self._queue_failures} 項。",
                            "success" if not self._queue_failures else "error")
            return
        request, info = self.queue_list.takeItem(0).data(QtCore.Qt.UserRole)
        self.refresh_queue()
        self.start_task("download", {"request": request, "info": info})

    def open_last_file(self):
        if self._last_files and Path(self._last_files[-1]).is_file():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self._last_files[-1]))
        else:
            self.set_status("完成的檔案已移動或不存在。", "error")

    def open_folder(self):
        folder = str(Path(self._last_files[-1]).parent) if self._last_files else self.path_input.text()
        if Path(folder).is_dir():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))

    def save_log(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "儲存工作紀錄", "yt-dlp-log.txt", "文字檔 (*.txt)")
        if path:
            try:
                Path(path).write_text(self.log_box.toPlainText(), encoding="utf-8")
            except OSError as error:
                self.set_status(f"無法儲存紀錄：{error}", "error")

    def closeEvent(self, event):
        if self._worker is not None:
            self._closing = True
            self.cancel_task()
            self.set_status("正在停止工作，清理完成後會自動關閉...", "cancelled")
            event.ignore()
            return
        self.save_settings()
        super().closeEvent(event)


def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("yt-dlp GUI Downloader")
    app.setApplicationVersion(core.VERSION)
    window = YtDlpGui()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
