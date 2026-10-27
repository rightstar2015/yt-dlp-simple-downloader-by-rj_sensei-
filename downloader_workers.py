"""Cancellable background operations; widgets are only changed by GUI slots."""
from collections import deque
import glob
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import traceback
import zipfile

import requests
from PyQt5 import QtCore
import downloader_core as core
import live_chat


class Cancelled(Exception):
    pass


class TaskWorker(QtCore.QThread):
    status_changed = QtCore.pyqtSignal(str)
    progress_changed = QtCore.pyqtSignal(int, str)
    log_message = QtCore.pyqtSignal(str)
    result_ready = QtCore.pyqtSignal(bool, object, str)

    def __init__(self, operation, params=None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.params = params or {}
        self.cancel_event = threading.Event()
        self._proc = None
        self._files = []
        self._metadata = None
        self._chat_files = []
        self._no_chat = False

    def cancel(self):
        self.cancel_event.set()

    def check_cancelled(self):
        if self.cancel_event.is_set():
            message = "工作已取消。"
            if self.operation == "download":
                message += "已完成的檔案與可續傳的部分檔案會保留。"
            raise Cancelled(message)

    def run(self):
        try:
            data, message = getattr(self, "do_" + self.operation)()
            self.result_ready.emit(True, data, message)
        except Cancelled as error:
            self.log_message.emit(str(error))
            self.result_ready.emit(False, {"cancelled": True, "files": self._files}, str(error))
        except Exception as error:
            self.log_message.emit(traceback.format_exc())
            self.result_ready.emit(False, {"files": self._files}, str(error))
        finally:
            if self._proc is not None and self._proc.poll() is None:
                self._stop_process(self._proc)
            self._proc = None

    def _start_process(self, command, separate_stderr=True):
        self.check_cancelled()
        flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
        self._proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE if separate_stderr else subprocess.STDOUT,
                                      text=True, encoding="utf-8", errors="replace",
                                      bufsize=1, creationflags=flags,
                                      start_new_session=os.name != "nt")
        return self._proc

    def _stop_process(self, process):
        if process.poll() is not None:
            return
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, timeout=5,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
        else:
            import signal
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                import signal
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait(timeout=3)

    def capture(self, command, timeout=30):
        process = self._start_process(command)
        deadline = time.monotonic() + timeout
        try:
            while True:
                self.check_cancelled()
                if time.monotonic() > deadline:
                    raise TimeoutError(f"工具等候超過 {timeout} 秒，請稍後再試。")
                try:
                    stdout, stderr = process.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if stderr.strip():
                self.log_message.emit(stderr.strip())
            if process.returncode:
                raise RuntimeError(f"工具退出碼 {process.returncode}：\n{stderr.strip()[-4000:] or stdout.strip()[-4000:]}")
            return stdout
        finally:
            if process.poll() is None:
                self._stop_process(process)
            process.stdout.close()
            process.stderr.close()
            self._proc = None

    def validate_binary(self, path, argument):
        self.check_cancelled()
        output = self.capture([str(path), argument], timeout=15).strip()
        if not output:
            raise ValueError(f"工具驗證失敗：{Path(path).name} 沒有回傳版本。")
        return output.splitlines()[0]

    def download_file(self, url, path):
        self.check_cancelled()
        with requests.get(url, stream=True, timeout=(10, 15),
                          headers={"Accept-Encoding": "identity"}) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0
            last_progress = None
            with open(path, "wb") as target:
                for chunk in response.iter_content(chunk_size=65536):
                    self.check_cancelled()
                    if not chunk:
                        continue
                    target.write(chunk)
                    downloaded += len(chunk)
                    percent = min(99, int(downloaded * 100 / total)) if total else -1
                    marker = (percent, downloaded // (1024 * 1024))
                    if marker != last_progress:
                        self.progress_changed.emit(percent, f"已下載 {core.format_size(downloaded)}" +
                                                   (f" / {core.format_size(total)}" if total else ""))
                        last_progress = marker
            if not downloaded or (total and total != downloaded):
                raise ValueError("下載檔案不完整；原工具未變更，請重新嘗試。")
        self.check_cancelled()

    def do_update(self):
        core.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.status_changed.emit("正在查詢 yt-dlp 最新版本...")
        release = {}
        try:
            with requests.get(core.YT_DLP_API, timeout=(5, 10)) as response:
                response.raise_for_status()
                release = response.json()
                if not isinstance(release, dict):
                    release = {}
        except (requests.RequestException, ValueError) as error:
            self.log_message.emit(f"版本 API 無法使用，改由官方下載網址更新：{error}")
        self.check_cancelled()
        with tempfile.TemporaryDirectory(prefix="ytdlp-update-", dir=core.APP_DATA_DIR) as temp:
            staged = Path(temp) / "yt-dlp.exe"
            self.status_changed.emit(f"正在下載 yt-dlp {release.get('tag_name', '最新版')}...")
            self.download_file(core.YT_DLP_URL, staged)
            asset = next((a for a in release.get("assets", []) if a.get("name") == "yt-dlp.exe"), {})
            digest = asset.get("digest") or ""
            if digest.startswith("sha256:"):
                with staged.open("rb") as source:
                    actual = hashlib.sha256(source.read()).hexdigest()
                if actual != digest.split(":", 1)[1]:
                    raise ValueError("yt-dlp SHA-256 驗證失敗；原工具未變更。")
            self.status_changed.emit("正在驗證新 yt-dlp...")
            version = self.validate_binary(staged, "--version")
            self.check_cancelled()
            os.replace(staged, core.APP_DATA_DIR / "yt-dlp.exe")
        self.progress_changed.emit(100, "更新完成")
        return {"version": version}, f"yt-dlp 更新完成，版本：{version}"

    def do_ffmpeg(self):
        core.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ffmpeg-install-", dir=core.APP_DATA_DIR) as temp:
            temp = Path(temp)
            archive = temp / "ffmpeg.zip"
            self.status_changed.emit("正在下載 FFmpeg 套件...")
            self.download_file(core.FFMPEG_URL, archive)
            self.status_changed.emit("正在解壓 FFmpeg 與 FFprobe...")
            found = set()
            with zipfile.ZipFile(archive) as zipped:
                for member in zipped.infolist():
                    name = Path(member.filename).name
                    if name not in ("ffmpeg.exe", "ffprobe.exe") or member.is_dir():
                        continue
                    if name in found:
                        raise ValueError("FFmpeg 壓縮檔有重複的工具檔案。")
                    with zipped.open(member) as source, (temp / name).open("wb") as target:
                        while True:
                            self.check_cancelled()
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            target.write(chunk)
                    found.add(name)
            if found != {"ffmpeg.exe", "ffprobe.exe"}:
                raise ValueError("FFmpeg 壓縮檔缺少必要工具，原有工具未變更。")
            self.status_changed.emit("正在驗證 FFmpeg 與 FFprobe...")
            for name in sorted(found):
                self.log_message.emit(self.validate_binary(temp / name, "-version"))
            self.check_cancelled()
            replaced = []
            old_files = {}
            try:
                for name in sorted(found):
                    destination = core.APP_DATA_DIR / name
                    if destination.exists():
                        backup = temp / (name + ".backup")
                        shutil.copy2(destination, backup)
                        old_files[name] = backup
                # 安裝兩個工具期間不取消，避免只更新其中一個。
                for name in sorted(found):
                    os.replace(temp / name, core.APP_DATA_DIR / name)
                    replaced.append(name)
            except Exception:
                for name in reversed(replaced):
                    destination = core.APP_DATA_DIR / name
                    if name in old_files:
                        os.replace(old_files[name], destination)
                    else:
                        destination.unlink(missing_ok=True)
                raise
        self.progress_changed.emit(100, "安裝完成")
        return {}, "FFmpeg 與 FFprobe 已通過驗證並完成安裝。"

    def do_probe(self):
        self.status_changed.emit("正在背景檢查工具...")
        tools = core.resolve_tools(self.params.get("ffmpeg_dir", ""))
        versions = {}
        for name, path in list(tools.items()):
            self.check_cancelled()
            if not path:
                continue
            try:
                versions[name] = self.validate_binary(path, "--version" if name == "yt-dlp" else "-version")
            except Cancelled:
                raise
            except Exception as error:
                self.log_message.emit(f"{name} 驗證失敗：{error}")
                tools[name] = None
        latest = self.params.get("latest", "")
        checked = self.params.get("checked", 0)
        if tools.get("yt-dlp") and time.time() - checked > 24 * 3600:
            try:
                with requests.get(core.YT_DLP_API, timeout=(5, 10)) as response:
                    response.raise_for_status()
                    latest = response.json().get("tag_name", "")
                    checked = time.time()
            except (requests.RequestException, ValueError) as error:
                self.log_message.emit(f"更新查詢暫時無法使用：{error}")
        self.check_cancelled()
        return {"tools": tools, "versions": versions, "latest": latest, "checked": checked}, "工具檢查完成。"

    def get_info(self, url, ffmpeg_dir=""):
        tools = core.resolve_tools(ffmpeg_dir)
        if not tools.get("yt-dlp"):
            raise ValueError("請先更新／安裝 yt-dlp。")
        url = core.validate_url(url)
        self.status_changed.emit("正在取得影片資訊與格式清單...")
        command = core.base_command(tools["yt-dlp"]) + ["--dump-single-json", "--skip-download",
                                                       "--playlist-items", "1", "--", url]
        info = json.loads(self.capture(command, timeout=90))
        if info.get("_type") in ("playlist", "multi_video") or "entries" in info:
            raise ValueError("這是播放清單，請改用簡單模式並勾選「下載播放清單」。")
        return info

    def do_info(self):
        url = core.validate_url(self.params["url"])
        info = self.get_info(url, self.params.get("ffmpeg_dir", ""))
        return {"url": url, "info": info}, f"已取得：{info.get('title', '影片')}"

    def _download_line(self, line):
        if line.startswith("GUI_PROGRESS:"):
            try:
                data = json.loads(line.split(":", 1)[1])
                chat_file = data.get("filename") or ""
                if chat_file.endswith(live_chat.CHAT_SUFFIX) and chat_file not in self._chat_files:
                    self._chat_files.append(chat_file)
                    self.status_changed.emit("正在下載聊天室紀錄（直播進行中會持續記錄到結束，可按取消停止並保留）...")
                downloaded = data.get("downloaded_bytes") or 0
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                percent = min(100, int(downloaded * 100 / total)) if total else -1
                eta = data.get("eta")
                speed = data.get("speed")
                text = f"{core.format_size(downloaded)}" + (f" / {core.format_size(total)}" if total else "")
                if speed:
                    text += f" | {core.format_size(speed)}/s"
                if eta is not None:
                    text += f" | 剩餘約 {int(eta)} 秒"
                self.progress_changed.emit(percent, text)
            except (ValueError, TypeError, OverflowError):
                self.log_message.emit(line)
        elif line.startswith("GUI_POST:"):
            if self.params["request"].chat_only:
                return  # 只下載聊天室時沒有影音處理，只是 yt-dlp 的檔案整理步驟。
            self.status_changed.emit("正在合併／轉檔，請稍候...")
            self.progress_changed.emit(-1, "影音處理中；轉檔可能需要較長時間")
        elif line.startswith("GUI_FILE:"):
            try:
                path = json.loads(line.split(":", 1)[1])
                if isinstance(path, str):
                    self._files.append(path)
                    self.log_message.emit(f"已完成檔案：{path}")
            except ValueError:
                self.log_message.emit(line)
        elif line.startswith("GUI_META:"):
            try:
                self._metadata = json.loads(line.split(":", 1)[1])
                target = "聊天室" if self.params["request"].chat_only else ""
                self.status_changed.emit(f"正在下載{target}：{self._metadata.get('title', '影片')}")
            except (ValueError, AttributeError):
                self.log_message.emit(line)
        elif line:
            if "There are no subtitles for the requested languages" in line:
                self._no_chat = True
            self.log_message.emit(line)

    def _finish_chat(self, request, cancel_check=None):
        """Turn recorded chat into final files; returns a note for the result message."""
        if not request.chat:
            return ""
        outputs = []
        for path in self._chat_files:
            final = Path(path)
            partial = Path(path + ".part")
            if not final.is_file() and partial.is_file():
                # 中斷錄製的聊天室每行仍是完整 JSON，改回正式檔名保留已錄到的留言。
                os.replace(partial, final)
                self.log_message.emit(f"已保留中斷前錄到的聊天室：{final}")
            for fragment in final.parent.glob(glob.escape(final.name) + ".part-Frag*"):
                fragment.unlink(missing_ok=True)
            if not final.is_file():
                continue
            outputs.append(str(final))
            self.log_message.emit(f"已完成聊天室紀錄：{final}")
            if request.chat_text:
                self.status_changed.emit("正在轉存聊天室文字檔...")
                text_path, count = live_chat.convert_file(final, cancel_check=cancel_check)
                outputs.append(text_path)
                self.log_message.emit(f"已轉存 {count} 則留言：{text_path}")
        self._files[:0] = outputs
        if outputs:
            return ""
        reason = "此影片沒有可下載的聊天室紀錄（可能不是直播／首播、聊天室已關閉，或網站不支援）。"
        if request.chat_only:
            raise RuntimeError(reason)
        self.log_message.emit(reason)
        return "（此影片沒有聊天室紀錄）"

    def do_download(self):
        request = self.params["request"]
        tools = core.resolve_tools(request.ffmpeg_dir)
        info = self.params.get("info")
        command = core.build_download_command(request, tools, info)
        if request.clip and not info:
            info = self.get_info(request.url, request.ffmpeg_dir)
            command = core.build_download_command(request, tools, info)
        self.status_changed.emit("開始下載...")
        self.log_message.emit(core.estimate_size(request, info))
        self.log_message.emit("執行：" + subprocess.list2cmdline(command))
        process = self._start_process(command, separate_stderr=False)
        lines = queue.Queue(maxsize=200)
        tail = deque(maxlen=30)

        def read_output():
            try:
                for line in process.stdout:
                    while not self.cancel_event.is_set():
                        try:
                            lines.put(line.rstrip(), timeout=0.1)
                            break
                        except queue.Full:
                            pass
            finally:
                while not self.cancel_event.is_set():
                    try:
                        lines.put(None, timeout=0.1)
                        break
                    except queue.Full:
                        pass

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        ended = False
        finished = False
        try:
            while not ended:
                self.check_cancelled()
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    if process.poll() is not None and not reader.is_alive() and lines.empty():
                        break
                    continue
                if line is None:
                    ended = True
                else:
                    if not line.startswith("GUI_PROGRESS:"):
                        tail.append(line)
                    self._download_line(line)
            while process.poll() is None:
                self.check_cancelled()
                time.sleep(0.05)
            self.check_cancelled()
            if process.returncode:
                raise RuntimeError(f"下載失敗，工具退出碼 {process.returncode}：\n" + "\n".join(tail)[-4000:])
            finished = True
            note = self._finish_chat(request, self.check_cancelled)
            self.progress_changed.emit(100, "下載完成")
            return {"files": self._files, "metadata": self._metadata}, "下載完成！" + note
        finally:
            if process.poll() is None:
                self._stop_process(process)
            reader.join(timeout=2)
            process.stdout.close()
            self._proc = None
            if not finished and self.cancel_event.is_set() and self._chat_files:
                try:
                    self._finish_chat(request)
                except Exception as error:
                    self.log_message.emit(f"保留聊天室紀錄失敗：{error}")
