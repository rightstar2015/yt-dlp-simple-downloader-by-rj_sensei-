import sys
import os
import subprocess
import requests
import re
from PyQt5 import QtWidgets, QtCore

GITHUB_YT_DLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
LOCAL_YT_DLP = os.path.join(os.path.dirname(__file__), "yt-dlp.exe")


class YtDlpGui(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("yt-dlp GUI")
        self.init_ui()
        self.resize(900, 700)
        self.setFixedWidth(900)

    def init_ui(self):
        container_layout = QtWidgets.QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用 QScrollArea 防止窗口被動態內容撐大
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        
        scroll_widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout()
        scroll_widget.setLayout(self.layout)
        scroll.setWidget(scroll_widget)
        
        # 進度條與預估剩餘時間（初始隱藏）
        progress_layout = QtWidgets.QHBoxLayout()
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(20)
        progress_layout.addWidget(self.progress_bar)
        self.eta_label = QtWidgets.QLabel("")
        self.eta_label.setVisible(False)
        progress_layout.addWidget(self.eta_label)
        self.layout.addLayout(progress_layout)
        
        # 影片網址
        self.url_label = QtWidgets.QLabel("影片網址：")
        self.url_input = QtWidgets.QLineEdit()
        self.layout.addWidget(self.url_label)
        self.layout.addWidget(self.url_input)

        # 下載位置
        path_layout = QtWidgets.QHBoxLayout()
        self.path_label = QtWidgets.QLabel("下載位置：")
        self.path_input = QtWidgets.QLineEdit(os.getcwd())
        self.path_btn = QtWidgets.QPushButton("選擇...")
        self.path_btn.clicked.connect(self.choose_folder)
        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.path_btn)
        self.layout.addLayout(path_layout)

        # 檔案名稱
        name_layout = QtWidgets.QHBoxLayout()
        self.name_label = QtWidgets.QLabel("檔案名稱(可選)：")
        self.name_input = QtWidgets.QLineEdit()
        name_layout.addWidget(self.name_label)
        name_layout.addWidget(self.name_input)
        self.layout.addLayout(name_layout)

        # 下載模式
        self.mode_group = QtWidgets.QGroupBox("下載模式")
        mode_layout = QtWidgets.QHBoxLayout()
        self.full_radio = QtWidgets.QRadioButton("全片下載")
        self.full_radio.setChecked(True)
        self.clip_radio = QtWidgets.QRadioButton("指定時間下載")
        mode_layout.addWidget(self.full_radio)
        mode_layout.addWidget(self.clip_radio)
        self.mode_group.setLayout(mode_layout)
        self.layout.addWidget(self.mode_group)

        # 片段時間
        self.time_group = QtWidgets.QGroupBox("下載片段時間 (僅片段模式)")
        time_layout = QtWidgets.QHBoxLayout()
        self.start_label = QtWidgets.QLabel("開始時間(00:00:00)：")
        self.start_input = QtWidgets.QLineEdit()
        self.end_label = QtWidgets.QLabel("結束時間(00:00:00)：")
        self.end_input = QtWidgets.QLineEdit()
        time_layout.addWidget(self.start_label)
        time_layout.addWidget(self.start_input)
        time_layout.addWidget(self.end_label)
        time_layout.addWidget(self.end_input)
        self.time_group.setLayout(time_layout)
        self.layout.addWidget(self.time_group)

        # 模式切換（互斥）
        mode_switch_layout = QtWidgets.QHBoxLayout()
        self.mode_group_btn = QtWidgets.QButtonGroup(self)
        self.simple_mode_radio = QtWidgets.QRadioButton("簡單模式")
        self.advanced_mode_radio = QtWidgets.QRadioButton("進階模式")
        self.simple_mode_radio.setChecked(True)
        self.mode_group_btn.addButton(self.simple_mode_radio)
        self.mode_group_btn.addButton(self.advanced_mode_radio)
        mode_switch_layout.addWidget(self.simple_mode_radio)
        mode_switch_layout.addWidget(self.advanced_mode_radio)
        self.layout.addLayout(mode_switch_layout)
        
        # 模式提示
        self.mode_hint = QtWidgets.QLabel()
        self.layout.addWidget(self.mode_hint)
        
        # 合併影音選項（進階模式專用）
        self.merge_checkbox = QtWidgets.QCheckBox("是否合併成單個影音檔（預設勾選）")
        self.merge_checkbox.setChecked(True)
        self.layout.addWidget(self.merge_checkbox)

        # 簡單模式格式選擇
        self.simple_fmt_layout = QtWidgets.QHBoxLayout()
        self.fmt_label = QtWidgets.QLabel("下載格式：")
        self.fmt_combo = QtWidgets.QComboBox()
        self.fmt_combo.addItems(["mp4", "mp3", "m4a"])
        self.simple_fmt_layout.addWidget(self.fmt_label)
        self.simple_fmt_layout.addWidget(self.fmt_combo)
        self.layout.addLayout(self.simple_fmt_layout)

        # 進階模式格式選擇（分為影片/音頻）
        self.advanced_fmt_group = QtWidgets.QGroupBox("進階模式格式選擇 (僅進階模式)")
        adv_fmt_vbox = QtWidgets.QVBoxLayout()
        
        # 取得格式按鈕
        self.fmt_refresh_btn = QtWidgets.QPushButton("取得格式清單")
        self.fmt_refresh_btn.clicked.connect(self.fetch_formats)
        adv_fmt_vbox.addWidget(self.fmt_refresh_btn)
        
        # 影片格式選擇區
        video_label_title = QtWidgets.QLabel("影片格式（單選）")
        video_label_title.setStyleSheet("font-weight: bold;")
        adv_fmt_vbox.addWidget(video_label_title)
        self.video_format_layout = QtWidgets.QVBoxLayout()
        adv_fmt_vbox.addLayout(self.video_format_layout)
        
        # 音頻格式選擇區
        audio_label_title = QtWidgets.QLabel("音頻格式（單選）")
        audio_label_title.setStyleSheet("font-weight: bold;")
        adv_fmt_vbox.addWidget(audio_label_title)
        self.audio_format_layout = QtWidgets.QVBoxLayout()
        adv_fmt_vbox.addLayout(self.audio_format_layout)
        
        self.advanced_fmt_group.setLayout(adv_fmt_vbox)
        self.layout.addWidget(self.advanced_fmt_group)

        # 下載按鈕
        self.download_btn = QtWidgets.QPushButton("下載影片")
        self.download_btn.clicked.connect(self.download_video)
        self.layout.addWidget(self.download_btn)

        self.update_btn = QtWidgets.QPushButton("自動更新 yt-dlp")
        self.update_btn.clicked.connect(self.update_ytdlp)
        self.layout.addWidget(self.update_btn)

        # 備註欄位
        note_text = "ℹ️ 這是一款簡單的下載器，若是填了網址照做發現錯誤請先按下更新yt-dlp\n若有任何相關問題請於X上面回報 @rj_sensei_"
        self.note = QtWidgets.QLabel(note_text)
        self.note.setStyleSheet("background-color: #f0f8ff; border: 1px solid #4a90e2; border-radius: 5px; padding: 8px; color: #333;")
        self.note.setWordWrap(True)
        self.layout.addWidget(self.note)

        self.status = QtWidgets.QLabel("")
        self.layout.addWidget(self.status)
        
        # 添加伸縮空間防止窗口被撐大
        self.layout.addStretch()
        
        scroll.setWidget(scroll_widget)
        container_layout.addWidget(scroll)
        self.setLayout(container_layout)
        
        self.clip_radio.toggled.connect(self.toggle_time_group)
        self.simple_mode_radio.toggled.connect(self.toggle_mode)
        self.advanced_mode_radio.toggled.connect(self.toggle_mode)
        self.toggle_time_group()
        self.toggle_mode()

    def toggle_time_group(self):
        self.time_group.setEnabled(self.clip_radio.isChecked())

    def toggle_mode(self):
        is_simple = self.simple_mode_radio.isChecked()
        for i in range(self.simple_fmt_layout.count()):
            widget = self.simple_fmt_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(is_simple)
        self.advanced_fmt_group.setVisible(not is_simple)
        self.merge_checkbox.setVisible(not is_simple)
        if is_simple:
            self.mode_hint.setText("簡單模式請直接貼上連結並按下下載影片即可")
        else:
            self.mode_hint.setText("進階模式則貼上連結後先選擇取得格式清單再下載")

    def choose_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "選擇下載資料夾", self.path_input.text())
        if folder:
            self.path_input.setText(folder)

    def fetch_formats(self):
        url = self.url_input.text().strip()
        if not url:
            self.status.setText("請先輸入影片網址！")
            return
        if not os.path.exists(LOCAL_YT_DLP):
            self.status.setText("yt-dlp 不存在，請先點擊自動更新下載！")
            return
        self.status.setText("正在取得格式清單...")
        QtWidgets.QApplication.processEvents()
        cmd = [LOCAL_YT_DLP, url, "-F"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            lines = result.stdout.splitlines()
            
            # 清空舊的單選按鈕
            self.clear_layout(self.video_format_layout)
            self.clear_layout(self.audio_format_layout)
            
            # 創建新的單選按鈕組
            self.video_button_group = QtWidgets.QButtonGroup()
            self.audio_button_group = QtWidgets.QButtonGroup()
            
            video_count = 0
            audio_count = 0
            
            for line in lines:
                line = line.strip()
                # 只處理以數字開頭的行（格式行）
                if not line or not line[0].isdigit():
                    continue
                    
                parts = line.split()
                if len(parts) < 2:
                    continue
                
                fmt_id = parts[0]
                ext = parts[1] if len(parts) > 1 else ""
                
                # 判斷是音頻還是影片：檢查第2-3個欄位是否為 "audio only"
                is_audio_only = len(parts) > 2 and parts[2] == "audio" and len(parts) > 3 and parts[3] == "only"
                
                # 提取解析度、編碼等信息
                resolution = ""
                vcodec = ""
                acodec = ""
                filesize = ""
                
                # 尋找 "|" 分隔符的位置
                pipe_indices = [i for i, p in enumerate(parts) if p == "|"]
                
                if is_audio_only:
                    # 音頻格式：ID ext audio only ... | 檔案大小... | 音頻編碼
                    # 檔案大小在第一個 | 之後
                    if len(pipe_indices) >= 1:
                        for i in range(pipe_indices[0] + 1, pipe_indices[1] if len(pipe_indices) > 1 else len(parts)):
                            if "MiB" in parts[i] or "KiB" in parts[i] or "GiB" in parts[i]:
                                filesize = parts[i]
                                break
                    # 音頻編碼應在第二個 | 之後
                    if len(pipe_indices) >= 2:
                        idx = pipe_indices[1] + 1
                        if idx < len(parts):
                            acodec = parts[idx]
                else:
                    # 影片格式：ID ext resolution fps ... | 檔案大小... | 視頻編碼 音頻編碼...
                    resolution = parts[2] if len(parts) > 2 and parts[2] != "audio" else ""
                    # 檔案大小在第一個 | 之後
                    if len(pipe_indices) >= 1:
                        for i in range(pipe_indices[0] + 1, pipe_indices[1] if len(pipe_indices) > 1 else len(parts)):
                            if "MiB" in parts[i] or "KiB" in parts[i] or "GiB" in parts[i]:
                                filesize = parts[i]
                                break
                    # 視頻編碼在第二個 | 之後
                    if len(pipe_indices) >= 2:
                        idx = pipe_indices[1] + 1
                        if idx < len(parts):
                            vcodec = parts[idx]
                    # 音頻編碼在視頻編碼之後
                    if vcodec and len(pipe_indices) >= 2:
                        idx = pipe_indices[1] + 2
                        if idx < len(parts):
                            acodec = parts[idx]
                
                # 根據是否為音頻創建按鈕
                if is_audio_only:
                    btn_text = f"{ext.upper()} | {acodec} | {filesize}"
                    btn = QtWidgets.QRadioButton(btn_text)
                    btn.fmt_id = fmt_id
                    self.audio_button_group.addButton(btn, audio_count)
                    self.audio_format_layout.addWidget(btn)
                    audio_count += 1
                elif resolution and vcodec:  # 只要有解析度和視頻編碼就認為是影片
                    btn_text = f"{resolution} | {ext} | {filesize} | {vcodec}"
                    btn = QtWidgets.QRadioButton(btn_text)
                    btn.fmt_id = fmt_id
                    self.video_button_group.addButton(btn, video_count)
                    self.video_format_layout.addWidget(btn)
                    video_count += 1
            
            if video_count == 0 and audio_count == 0:
                self.status.setText("未找到可用格式")
            else:
                self.status.setText(f"格式清單已更新 (影片:{video_count}種, 音頻:{audio_count}種)")
        except Exception as e:
            self.status.setText(f"取得格式失敗: {e}")
    
    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def download_video(self):
        url = self.url_input.text().strip()
        if not url:
            self.status.setText("請先輸入影片網址！")
            return
        out_path = self.path_input.text().strip()
        if not os.path.isdir(out_path):
            self.status.setText("下載路徑不存在！")
            return
        out_name = self.name_input.text().strip()
        if out_name:
            out_tpl = os.path.join(out_path, out_name + ".%(ext)s")
        else:
            out_tpl = os.path.join(out_path, "%(title)s.%(ext)s")
        cmd = [LOCAL_YT_DLP, url, "-o", out_tpl]
        # 模式判斷
        if self.simple_mode_radio.isChecked():
            fmt = self.fmt_combo.currentText()
            if fmt == "mp4":
                cmd += ["-f", "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4][vcodec^=avc1]/best"]
            elif fmt == "mp3":
                cmd += ["-x", "--audio-format", "mp3"]
            elif fmt == "m4a":
                cmd += ["-x", "--audio-format", "m4a"]
        else:
            # 進階模式
            video_btn = self.video_button_group.checkedButton() if hasattr(self, 'video_button_group') else None
            audio_btn = self.audio_button_group.checkedButton() if hasattr(self, 'audio_button_group') else None
            
            if not video_btn and not audio_btn:
                self.status.setText("請先在進階模式中選擇影片或音頻格式！")
                return
            
            fmt_str = ""
            if video_btn:
                fmt_str += video_btn.fmt_id
            if audio_btn:
                if fmt_str:
                    fmt_str += "+"
                fmt_str += audio_btn.fmt_id
            
            if fmt_str:
                cmd += ["-f", fmt_str]
            
            if not self.merge_checkbox.isChecked():
                cmd += ["--allow-unplayable-formats", "--no-merge-output"]
        # 片段下載
        if self.clip_radio.isChecked():
            start = self.start_input.text().strip()
            end = self.end_input.text().strip()
            if start:
                cmd += ["--download-sections", f"*{start}-{end if end else ''}"]
        self.status.setText("開始下載...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.eta_label.setText("")
        QtWidgets.QApplication.processEvents()
        try:
            progress_re = re.compile(r"\[download\]\s+(\d+\.\d+)%.*?ETA\s+([\d:]+)?")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                line = line.strip()
                self.status.setText(line)
                m = progress_re.search(line)
                if m:
                    percent = float(m.group(1))
                    self.progress_bar.setValue(int(percent))
                    eta = m.group(2) if m.group(2) else ""
                    self.eta_label.setText(f"預估剩餘時間: {eta}")
                QtWidgets.QApplication.processEvents()
            proc.wait()
            self.progress_bar.setVisible(False)
            self.eta_label.setText("")
            if proc.returncode == 0:
                self.status.setText("下載完成！")
            else:
                self.status.setText("下載失敗！")
        except Exception as e:
            self.progress_bar.setVisible(False)
            self.eta_label.setText("")
            self.status.setText(f"下載失敗: {e}")

    def update_ytdlp(self):
        self.status.setText("正在下載 yt-dlp 最新版...")
        QtWidgets.QApplication.processEvents()
        try:
            r = requests.get(GITHUB_YT_DLP_URL, stream=True)
            with open(LOCAL_YT_DLP, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            self.status.setText("yt-dlp 已更新！")
        except Exception as e:
            self.status.setText(f"更新失敗: {e}")


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = YtDlpGui()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
