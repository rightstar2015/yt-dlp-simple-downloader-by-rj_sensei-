"""Offline regression suite, real Qt event loop and real child-process checks."""
from dataclasses import replace
from datetime import datetime
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt5 import QtCore, QtWidgets
import requests
import downloader_core as core
from downloader_workers import TaskWorker
import live_chat
import main


INFO = {"id": "sample", "title": "測試影片", "duration": 100, "formats": [
    {"format_id": "v-high", "ext": "mp4", "vcodec": "avc1.640028", "acodec": "none", "height": 1080, "filesize": 1000000},
    {"format_id": "a-main", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 128, "filesize": 100000},
    {"format_id": "mux", "ext": "mp4", "vcodec": "avc1.42001e", "acodec": "mp4a.40.2", "height": 360, "filesize": 400000},
    {"format_id": "story", "ext": "mhtml", "vcodec": "none", "acodec": "none"},
    {"format_id": "protected", "vcodec": "avc1", "acodec": "none", "has_drm": True},
]}
TOOLS = {"yt-dlp": "yt-dlp.exe", "ffmpeg": "C:/tools/ffmpeg.exe", "ffprobe": "C:/tools/ffprobe.exe"}


def chat_action(kind, **renderer):
    renderer.setdefault("authorName", {"simpleText": "@viewer"})
    renderer.setdefault("timestampUsec", "1793064797000000")
    return {"addChatItemAction": {"item": {kind: renderer}}}


# 與 yt-dlp 寫出的 .live_chat.json 相同：每行一個 JSON，重播的時間軸放在 replayChatItemAction 內。
CHAT_LINES = [
    {"replayChatItemAction": {"videoOffsetTimeMsec": "65000", "actions": [chat_action(
        "liveChatTextMessageRenderer", message={"runs": [{"text": "hello "}, {"emoji": {"emojiId": "👋"}}]})]}},
    {"replayChatItemAction": {"videoOffsetTimeMsec": "3725000", "actions": [chat_action(
        "liveChatPaidMessageRenderer", authorName={"simpleText": "@fan"}, purchaseAmountText={"simpleText": "NT$75"},
        message={"runs": [{"text": "nice"}, {"emoji": {"isCustomEmoji": True, "emojiId": "UC/x", "shortcuts": [":_wave:"]}}]})]}},
    {"replayChatItemAction": {"videoOffsetTimeMsec": "70000", "actions": [chat_action(
        "liveChatMembershipItemRenderer", headerSubtext={"runs": [{"text": "Welcome to "}, {"text": "Club"}]})]}},
    {"replayChatItemAction": {"videoOffsetTimeMsec": "71000", "actions": [
        {"addLiveChatTickerItemAction": {"item": {"liveChatTickerPaidMessageItemRenderer": {}}}},
        chat_action("liveChatViewerEngagementMessageRenderer")]}},
]


class Response:
    def __init__(self, content=b"MZvalid", total=None, error=None, delay=0, chunks=None):
        self.content = content
        self.chunks = chunks
        self.error = error
        self.delay = delay
        self.headers = {} if total is None else {"content-length": str(total)}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return {"tag_name": "2026.10.02", "assets": []}

    def iter_content(self, chunk_size):
        for chunk in self.chunks if self.chunks is not None else [self.content]:
            time.sleep(self.delay)
            yield chunk


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.request = core.DownloadRequest("https://www.youtube.com/watch?v=sample", self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def command(self, request=None):
        return core.build_download_command(request or self.request, TOOLS, INFO)

    def test_mp4_has_no_unrestricted_fallback_and_sets_container(self):
        cmd = self.command()
        selector = cmd[cmd.index("-f") + 1]
        self.assertTrue(all("ext=mp4" in branch and "avc1" in branch for branch in selector.split("/")))
        self.assertIn("--merge-output-format", cmd)
        self.assertIn("--remux-video", cmd)

    def test_separate_formats_use_comma_and_unique_filename(self):
        cmd = self.command(replace(self.request, mode="advanced", video_id="v-high", audio_id="a-main", merge=False))
        self.assertEqual(cmd[cmd.index("-f") + 1], "v-high,a-main")
        self.assertIn(".f%(format_id)s.", cmd[cmd.index("-o") + 1])
        self.assertNotIn("--no-merge-output", cmd)
        self.assertNotIn("--allow-unplayable-formats", cmd)

    def test_merged_formats_use_plus(self):
        cmd = self.command(replace(self.request, mode="advanced", video_id="v-high", audio_id="a-main"))
        self.assertEqual(cmd[cmd.index("-f") + 1], "v-high+a-main")

    def test_muxed_video_cannot_silently_ignore_selected_audio(self):
        with self.assertRaisesRegex(ValueError, "已含音訊"):
            self.command(replace(self.request, mode="advanced", video_id="mux", audio_id="a-main"))

    def test_single_download_is_explicit_and_progress_is_structured(self):
        cmd = self.command()
        self.assertIn("--no-playlist", cmd)
        self.assertIn("--playlist-items", cmd)
        self.assertIn("download:GUI_PROGRESS:%(progress)j", cmd)
        self.assertEqual(cmd[-2], "--")

    def test_playlist_custom_filename_has_index_and_id(self):
        cmd = self.command(replace(self.request, playlist=True, name="課程"))
        self.assertIn("--yes-playlist", cmd)
        filename = cmd[cmd.index("-o") + 1]
        self.assertIn("playlist_index", filename)
        self.assertIn("%(id)s", filename)

    def test_playlist_rejects_advanced_and_clip_modes(self):
        for changes in ({"mode": "advanced", "video_id": "v-high"}, {"clip": True, "start": "00:00:00"}):
            with self.assertRaises(ValueError):
                self.command(replace(self.request, playlist=True, **changes))

    def test_chat_with_video_adds_live_chat_subtitle_track(self):
        cmd = self.command(replace(self.request, chat=True))
        self.assertEqual(cmd[cmd.index("--sub-langs") + 1], "live_chat")
        self.assertIn("--write-subs", cmd)
        self.assertIn("-f", cmd)
        self.assertNotIn("--skip-download", cmd)

    def test_chat_only_skips_video_formats_and_ffmpeg(self):
        request = replace(self.request, mode="advanced", chat=True, chat_only=True, playlist=True,
                          url="https://www.youtube.com/@channel/streams")
        cmd = core.build_download_command(request, {"yt-dlp": "yt-dlp.exe"}, None)
        self.assertIn("--skip-download", cmd)
        self.assertIn("--write-subs", cmd)
        for flag in ("-f", "--merge-output-format", "--ffmpeg-location", "--download-sections"):
            self.assertNotIn(flag, cmd)
        self.assertIn("聊天室", core.estimate_size(request, INFO))

    def test_chat_only_rejects_clip_and_requires_chat(self):
        for changes in ({"chat": True, "chat_only": True, "clip": True, "start": "00:00:00"},
                        {"chat": False, "chat_only": True}):
            with self.assertRaises(ValueError):
                self.command(replace(self.request, **changes))

    def test_clip_without_end_uses_inf(self):
        cmd = self.command(replace(self.request, clip=True, start="00:00:10"))
        self.assertEqual(cmd[cmd.index("--download-sections") + 1], "*00:00:10-inf")

    def test_clip_rejects_invalid_time_order_and_duration(self):
        for start, end in [("00:60:00", ""), ("00:00:20", "00:00:10"), ("00:01:40", ""), ("00:00:00", "00:01:41")]:
            with self.assertRaises(ValueError):
                self.command(replace(self.request, clip=True, start=start, end=end))

    def test_clip_requires_ffmpeg_even_for_video_only(self):
        request = replace(self.request, mode="advanced", video_id="v-high", clip=True, start="00:00:00")
        with self.assertRaisesRegex(ValueError, "FFmpeg"):
            core.build_download_command(request, {"yt-dlp": "yt-dlp.exe"}, INFO)

    def test_separate_raw_formats_do_not_require_ffmpeg(self):
        request = replace(self.request, mode="advanced", video_id="v-high", audio_id="a-main", merge=False)
        self.assertTrue(core.build_download_command(request, {"yt-dlp": "yt-dlp.exe"}, INFO))

    def test_invalid_names_are_rejected(self):
        for name in ("../escape", "a/b", "x\\y", "CON", "con.txt", "nul", "bad.", "bad ", "a:b", "a\n", "a" * 161):
            with self.subTest(name=name), self.assertRaises(ValueError):
                core.validate_name(name)

    def test_percent_in_custom_name_is_literal(self):
        cmd = self.command(replace(self.request, name="100%完成"))
        self.assertIn("100%%完成", cmd[cmd.index("-o") + 1])

    def test_invalid_url_and_playlist_only_url_are_rejected(self):
        for url in ("", "file:///test", "https://", "https://a\n.b", "https://user:pass@example.com", "https://youtube.com/playlist?list=x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                core.validate_url(url)

    def test_non_youtube_http_urls_are_accepted(self):
        self.assertEqual(core.validate_url("https://vimeo.com/123"), "https://vimeo.com/123")

    def test_format_parser_preserves_nonnumeric_ids_and_excludes_storyboards_drm(self):
        video, audio = core.available_formats(INFO)
        self.assertEqual([f["format_id"] for f in video], ["v-high", "mux"])
        self.assertEqual([f["format_id"] for f in audio], ["a-main"])

    def test_estimation_uses_selected_streams_and_clip_duration(self):
        full = core.estimate_size(self.request, INFO)
        partial = core.estimate_size(replace(self.request, clip=True, start="00:00:00", end="00:00:10"), INFO)
        self.assertIn("1.0 MB", full)
        self.assertIn("107.4 KB", partial)

    def test_missing_format_size_is_not_reported_as_zero(self):
        info = {"formats": [{"format_id": "a", "acodec": "aac", "vcodec": "none"}]}
        self.assertIn("未知", core.estimate_size(replace(self.request, mode="mp3"), info))

    def test_ffmpeg_discovery_uses_complete_path_pair(self):
        directory = Path(self.temp.name)
        for name in ("ffmpeg.exe", "ffprobe.exe"):
            (directory / name).write_bytes(b"test")
        with patch.object(core, "APP_DATA_DIR", directory / "missing"), patch.object(core.shutil, "which", side_effect=lambda name: str(directory / (name + ".exe")) if name in ("ffmpeg", "ffprobe") else None):
            tools = core.resolve_tools()
        self.assertEqual(tools["ffmpeg"], str(directory / "ffmpeg.exe"))
        self.assertEqual(tools["ffprobe"], str(directory / "ffprobe.exe"))

    def test_bad_custom_ffmpeg_folder_does_not_silently_fall_back(self):
        with self.assertRaisesRegex(ValueError, "ffmpeg.exe"):
            core.resolve_tools(self.temp.name)


class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.paths = patch.multiple(core, APP_DATA_DIR=self.directory, PROJECT_DIR=self.directory)
        self.paths.start()
        self.probe_patch = patch.object(main.YtDlpGui, "update_dependencies_status")
        self.probe_patch.start()
        self.window = main.YtDlpGui(auto_check=False)
        self.window.path_input.setText(self.temp.name)
        self.window.url_input.setText("https://www.youtube.com/watch?v=sample")
        self.target = self.directory / "yt-dlp.exe"
        self.target.write_bytes(b"original")

    def tearDown(self):
        if self.window._worker is not None:
            self.window._worker.cancel()
            self.wait_until(lambda: self.window._worker is None)
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.probe_patch.stop()
        self.paths.stop()
        self.temp.cleanup()

    def wait_until(self, condition, timeout=8):
        deadline = time.monotonic() + timeout
        while not condition():
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail("Background task did not finish in time")
            time.sleep(0.005)
        self.app.processEvents()

    def run_update(self, download, validation="2026.10.02", api=None):
        with patch("downloader_workers.requests.get", side_effect=[api or Response(), download]):
            with patch.object(TaskWorker, "validate_binary", return_value=validation):
                self.window.update_ytdlp()
                self.wait_until(lambda: self.window._worker is None)
        self.assertTrue(self.window.download_btn.isEnabled())
        self.assertEqual(list(self.directory.glob("ytdlp-update-*")), [])

    def test_update_is_responsive_and_replaces_old_file_only_after_download(self):
        ticks = []
        timer = QtCore.QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start()
        try:
            self.run_update(Response(chunks=[b"MZ"] * 20, total=40, delay=0.02))
        finally:
            timer.stop()
        self.assertGreaterEqual(len(ticks), 10)
        self.assertEqual(self.target.read_bytes(), b"MZ" * 20)

    def test_http_error_preserves_old_binary(self):
        self.run_update(Response(error=requests.HTTPError("503")))
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertIn("503", self.window.log_box.toPlainText())

    def test_incomplete_and_empty_download_preserve_old_binary(self):
        for response in (Response(b"short", total=100), Response(b"")):
            self.run_update(response)
            self.assertEqual(self.target.read_bytes(), b"original")

    def test_api_failure_falls_back_to_official_download(self):
        self.run_update(Response(), api=requests.Timeout("API offline"))
        self.assertEqual(self.target.read_bytes(), b"MZvalid")

    def test_binary_validation_failure_preserves_old_binary(self):
        with patch("downloader_workers.requests.get", side_effect=[Response(), Response()]):
            with patch.object(TaskWorker, "validate_binary", side_effect=RuntimeError("invalid executable")):
                self.window.update_ytdlp()
                self.wait_until(lambda: self.window._worker is None)
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertEqual(list(self.directory.glob("ytdlp-update-*")), [])

    def test_duplicate_task_is_ignored_and_closing_cancels_update(self):
        self.window.show()
        with patch("downloader_workers.requests.get", side_effect=[Response(), Response(chunks=[b"x"] * 50, delay=0.02)]) as get:
            with patch.object(TaskWorker, "validate_binary") as validate:
                self.window.update_ytdlp()
                worker = self.window._worker
                self.window.download_ffmpeg()
                self.assertIs(self.window._worker, worker)
                QtCore.QTimer.singleShot(80, self.window.close)
                self.wait_until(lambda: self.window._worker is None)
                validate.assert_not_called()
                self.assertEqual(get.call_count, 2)
        self.assertFalse(self.window.isVisible())
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertEqual(list(self.directory.glob("ytdlp-update-*")), [])

    def make_zip(self, names=("ffmpeg.exe", "ffprobe.exe")):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as zipped:
            for name in names:
                zipped.writestr("package/bin/" + name, b"new " + name.encode())
        return output.getvalue()

    def install_ffmpeg(self, archive):
        with patch("downloader_workers.requests.get", return_value=Response(archive)):
            with patch.object(TaskWorker, "validate_binary", return_value="version test"):
                self.window.download_ffmpeg()
                self.wait_until(lambda: self.window._worker is None)

    def test_ffmpeg_validates_and_installs_both_executables(self):
        self.install_ffmpeg(self.make_zip())
        self.assertEqual((self.directory / "ffmpeg.exe").read_bytes(), b"new ffmpeg.exe")
        self.assertEqual((self.directory / "ffprobe.exe").read_bytes(), b"new ffprobe.exe")
        self.assertEqual(list(self.directory.glob("ffmpeg-install-*")), [])

    def test_ffmpeg_missing_probe_preserves_old_pair(self):
        for name in ("ffmpeg.exe", "ffprobe.exe"):
            (self.directory / name).write_bytes(b"old")
        self.install_ffmpeg(self.make_zip(("ffmpeg.exe",)))
        self.assertEqual((self.directory / "ffmpeg.exe").read_bytes(), b"old")
        self.assertEqual((self.directory / "ffprobe.exe").read_bytes(), b"old")

    def test_ffmpeg_second_replace_failure_rolls_back_first(self):
        for name in ("ffmpeg.exe", "ffprobe.exe"):
            (self.directory / name).write_bytes(b"old")
        original_replace = os.replace
        def fail_second(source, destination):
            if Path(source).name == "ffprobe.exe":
                raise PermissionError("ffprobe in use")
            return original_replace(source, destination)
        with patch("downloader_workers.os.replace", side_effect=fail_second):
            self.install_ffmpeg(self.make_zip())
        self.assertEqual((self.directory / "ffmpeg.exe").read_bytes(), b"old")
        self.assertEqual((self.directory / "ffprobe.exe").read_bytes(), b"old")

    def test_metadata_is_background_and_old_url_result_does_not_replace_new_selection(self):
        def capture(worker, command, timeout=30):
            time.sleep(0.1)
            return json.dumps(INFO)
        with patch.object(core, "resolve_tools", return_value=TOOLS), patch.object(TaskWorker, "capture", capture):
            self.window.fetch_formats()
            self.window.url_input.setText("https://vimeo.com/456")
            self.wait_until(lambda: self.window._worker is None)
        self.assertEqual(self.window.video_combo.count(), 1)
        self.assertIn("https://www.youtube.com/watch?v=sample", self.window._cache)
        self.window.url_input.setText("https://www.youtube.com/watch?v=sample")
        self.assertEqual(self.window.video_combo.count(), 3)

    def test_settings_remember_folder_format_and_window_is_resizable(self):
        self.window.fmt_combo.setCurrentText("mp3")
        self.window.save_settings()
        other = main.YtDlpGui(auto_check=False)
        try:
            self.assertEqual(other.path_input.text(), self.temp.name)
            self.assertEqual(other.fmt_combo.currentText(), "mp3")
            self.assertLess(other.minimumWidth(), other.maximumWidth())
        finally:
            other.close()
            other.deleteLater()

    def test_uncached_clip_checks_duration_in_background_before_download(self):
        self.window.clip_radio.setChecked(True)
        self.window.start_input.setText("00:01:40")
        with patch.object(core, "resolve_tools", return_value=TOOLS), patch.object(TaskWorker, "get_info", return_value=INFO) as get_info:
            with patch.object(TaskWorker, "_start_process") as start:
                self.window.download_video()
                self.wait_until(lambda: self.window._worker is None)
                start.assert_not_called()
                get_info.assert_called_once()
        self.assertIn("超出影片長度", self.window.status.text())

    def test_queue_saves_request_snapshot_and_processes_items_serially(self):
        seen = []
        def fake_download(worker):
            seen.append(worker.params["request"])
            time.sleep(0.03)
            return {"files": []}, "ok"
        self.window.fmt_combo.setCurrentText("mp3")
        self.window.add_to_queue()
        self.window.url_input.setText("https://vimeo.com/123")
        self.window.fmt_combo.setCurrentText("m4a")
        self.window.add_to_queue()
        with patch.object(TaskWorker, "do_download", fake_download):
            self.window.start_queue()
            self.wait_until(lambda: not self.window._queue_running and self.window._worker is None)
        self.assertEqual([request.mode for request in seen], ["mp3", "m4a"])
        self.assertEqual(self.window._queue_successes, 2)

    def test_capture_failure_retains_exit_code_and_stderr(self):
        worker = TaskWorker("info")
        with self.assertRaisesRegex(RuntimeError, "工具退出碼 7"):
            worker.capture([sys.executable, "-c", "import sys; print('bad input',file=sys.stderr); sys.exit(7)"])

    def test_download_structured_output_and_completed_path(self):
        output_file = self.directory / "complete.mp4"
        script = self.directory / "fake-download.py"
        script.write_text("import json,time,pathlib\n"
                          f"p=pathlib.Path({str(output_file)!r})\n"
                          "print('GUI_META:'+json.dumps({'title':'test'}),flush=True)\n"
                          "for i in range(20):\n"
                          " print('GUI_PROGRESS:'+json.dumps({'downloaded_bytes':i+1,'total_bytes':20,'eta':1,'speed':100}),flush=True)\n"
                          " time.sleep(.02)\n"
                          "p.write_bytes(b'done')\n"
                          "print('GUI_FILE:'+json.dumps(str(p)),flush=True)\n", encoding="utf-8")
        ticks = []
        timer = QtCore.QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start()
        progress_messages = []
        try:
            with patch.object(core, "resolve_tools", return_value=TOOLS), patch.object(core, "build_download_command", return_value=[sys.executable, str(script)]):
                self.window.download_video()
                self.window._worker.progress_changed.connect(lambda percent, message: progress_messages.append(message))
                self.wait_until(lambda: self.window._worker is None)
        finally:
            timer.stop()
        self.assertGreaterEqual(len(ticks), 10)
        self.assertEqual(self.window._last_files, [str(output_file)])
        self.assertTrue(self.window.open_file_btn.isEnabled())
        self.assertTrue(any("100.0 B/s" in message for message in progress_messages))

    def _chat_script(self, chat_file, live):
        script = self.directory / "fake-chat.py"
        lines = [json.dumps(line, ensure_ascii=False) for line in CHAT_LINES]
        script.write_text("import json,pathlib,time\n"
                          f"p=pathlib.Path({str(chat_file)!r})\n"
                          f"part=pathlib.Path({str(chat_file) + '.part'!r})\n"
                          f"lines={lines!r}\n"
                          "print('GUI_META:'+json.dumps({'title':'stream'}),flush=True)\n"
                          "pathlib.Path(str(part)+'-Frag3').write_text('x')\n"
                          "with part.open('w',encoding='utf-8') as f:\n"
                          " for line in lines:\n"
                          "  f.write(line+'\\n'); f.flush()\n"
                          "  print('GUI_PROGRESS:'+json.dumps({'downloaded_bytes':f.tell(),'filename':str(p)}),flush=True)\n"
                          + (" time.sleep(60)\n" if live else "part.replace(p)\n"), encoding="utf-8")
        return script

    def test_chat_only_download_converts_chat_to_text(self):
        chat_file = self.directory / "stream [id].live_chat.json"
        script = self._chat_script(chat_file, live=False)
        self.window.chat_checkbox.setChecked(True)
        self.window.chat_only_checkbox.setChecked(True)
        self.assertFalse(self.window.mode_group.isEnabled())
        self.assertEqual(self.window.download_btn.text(), "下載聊天室")
        with patch.object(core, "resolve_tools", return_value=TOOLS), patch.object(core, "build_download_command", return_value=[sys.executable, str(script)]):
            self.window.download_video()
            self.wait_until(lambda: self.window._worker is None)
        text_file = self.directory / "stream [id].live_chat.txt"
        self.assertEqual(self.window._last_files, [str(chat_file), str(text_file)])
        self.assertIn("[0:01:05] @viewer：hello 👋", text_file.read_text(encoding="utf-8-sig"))

    def test_chat_only_without_chat_track_reports_error(self):
        script = self.directory / "no-chat.py"
        script.write_text("print('[info] There are no subtitles for the requested languages',flush=True)\n", encoding="utf-8")
        self.window.chat_checkbox.setChecked(True)
        self.window.chat_only_checkbox.setChecked(True)
        with patch.object(core, "resolve_tools", return_value=TOOLS), patch.object(core, "build_download_command", return_value=[sys.executable, str(script)]):
            self.window.download_video()
            self.wait_until(lambda: self.window._worker is None)
        self.assertIn("沒有可下載的聊天室", self.window.status.text())

    def test_cancelled_live_chat_recording_is_kept_and_converted(self):
        chat_file = self.directory / "live [id].live_chat.json"
        script = self._chat_script(chat_file, live=True)
        self.window.chat_checkbox.setChecked(True)
        self.window.chat_only_checkbox.setChecked(True)
        with patch.object(core, "resolve_tools", return_value=TOOLS), patch.object(core, "build_download_command", return_value=[sys.executable, str(script)]):
            self.window.download_video()
            self.wait_until(lambda: self.window._worker is not None and len(self.window._worker._chat_files) == 1)
            time.sleep(0.3)
            self.window.cancel_task()
            self.wait_until(lambda: self.window._worker is None)
        self.assertTrue(chat_file.is_file())
        self.assertFalse(Path(str(chat_file) + ".part").exists())
        self.assertFalse(Path(str(chat_file) + ".part-Frag3").exists())
        text = (self.directory / "live [id].live_chat.txt").read_text(encoding="utf-8-sig")
        self.assertIn("[Super Chat NT$75] @fan：nice", text)

    @unittest.skipUnless(os.name == "nt", "Windows child-process tree cancellation")
    def test_cancel_kills_download_and_ffmpeg_like_child(self):
        child_pid_file = self.directory / "child.pid"
        script = self.directory / "parent.py"
        script.write_text("import pathlib,subprocess,sys,time\n"
                          "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
                          f"pathlib.Path({str(child_pid_file)!r}).write_text(str(child.pid))\n"
                          "time.sleep(60)\n", encoding="utf-8")
        with patch.object(core, "resolve_tools", return_value=TOOLS), patch.object(core, "build_download_command", return_value=[sys.executable, str(script)]):
            self.window.download_video()
            self.wait_until(child_pid_file.exists)
            child_pid = child_pid_file.read_text()
            self.window.cancel_task()
            self.wait_until(lambda: self.window._worker is None)
        result = subprocess.run(["tasklist", "/FI", "PID eq " + child_pid, "/FO", "CSV", "/NH"],
                                capture_output=True, text=True, encoding="mbcs", errors="replace", timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertNotIn('"' + child_pid + '"', result.stdout)
        self.assertTrue(self.window.download_btn.isEnabled())


class LiveChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name) / "video [id].live_chat.json"

    def tearDown(self):
        self.temp.cleanup()

    def convert(self, lines, tail=""):
        self.source.write_text("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines) + tail,
                               encoding="utf-8")
        path, count = live_chat.convert_file(self.source)
        return Path(path), count, Path(path).read_text(encoding="utf-8-sig").splitlines()

    def test_replay_messages_superchats_and_members_are_readable(self):
        path, count, lines = self.convert(CHAT_LINES)
        self.assertEqual(path.name, "video [id].live_chat.txt")
        self.assertEqual(count, 3)
        self.assertEqual(lines[1:], ["[0:01:05] @viewer：hello 👋",
                                     "[1:02:05] [Super Chat NT$75] @fan：nice:_wave:",
                                     "[0:01:10] [會員] @viewer：Welcome to Club"])

    def test_live_recording_uses_wall_clock_and_skips_truncated_line(self):
        line = {"replayChatItemAction": {"actions": [chat_action(
            "liveChatTextMessageRenderer", message={"simpleText": "第一行\n第二行"})]},
            "videoOffsetTimeMsec": "-8649133", "isLive": True}
        _, count, lines = self.convert([line], tail='{"replayChatItemAction": {"act')
        self.assertEqual(count, 1)
        expected = datetime.fromtimestamp(1793064797).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(lines[1], f"[{expected}] @viewer：第一行 第二行")


class StartupTests(unittest.TestCase):
    def test_startup_displays_before_slow_background_probe(self):
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as temp, patch.object(core, "APP_DATA_DIR", Path(temp)):
            def slow_probe(worker):
                time.sleep(0.3)
                return {"tools": {}, "versions": {}, "latest": "", "checked": 0}, "ready"
            with patch.object(TaskWorker, "do_probe", slow_probe):
                start = time.monotonic()
                window = main.YtDlpGui()
                window.show()
                self.assertLess(time.monotonic() - start, 0.25)
                app.processEvents()
                self.assertIsNotNone(window._worker)
                deadline = time.monotonic() + 3
                while window._worker is not None and time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(0.005)
                self.assertIsNone(window._worker)
                window.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
