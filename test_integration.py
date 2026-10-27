"""Actual yt-dlp CLI against a loopback-only fixture; no external downloads."""
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt5 import QtWidgets
import downloader_core as core
from downloader_workers import TaskWorker

TEST_EXE = os.environ.get("YT_DLP_TEST_EXE", "")


@unittest.skipUnless(TEST_EXE and Path(TEST_EXE).is_file(), "Set YT_DLP_TEST_EXE to an existing yt-dlp.exe")
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.files = {"/video.mp4": b"video fixture" * 16000, "/audio.m4a": b"audio fixture" * 8000}
        files = cls.files
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def respond(self, head=False):
                if self.path not in files:
                    self.send_error(404)
                    return
                body = files[self.path]
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4" if self.path.endswith("mp4") else "audio/mp4")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if not head:
                    try:
                        for offset in range(0, len(body), 4096):
                            self.wfile.write(body[offset:offset + 4096])
                            self.wfile.flush()
                            time.sleep(0.003)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
            def do_HEAD(self):
                self.respond(True)
            def do_GET(self):
                self.respond()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def run_worker(self, worker):
        results, progress, logs = [], [], []
        worker.result_ready.connect(lambda ok, data, text: results.append((ok, data, text)))
        worker.progress_changed.connect(lambda percent, text: progress.append((percent, text)))
        worker.log_message.connect(logs.append)
        worker.start()
        deadline = time.monotonic() + 30
        while worker.isRunning():
            self.app.processEvents()
            if time.monotonic() > deadline:
                worker.cancel()
                worker.wait(5000)
                self.fail("Integration worker timed out")
            time.sleep(0.005)
        self.app.processEvents()
        self.assertTrue(results, "Missing worker result")
        self.assertTrue(results[0][0], results[0][2] + "\n" + "\n".join(logs))
        worker.deleteLater()
        return results[0][1], progress

    def test_actual_json_metadata_and_format_parsing(self):
        worker = TaskWorker("info", {"url": self.url + "/video.mp4"})
        with patch.object(core, "resolve_tools", return_value={"yt-dlp": TEST_EXE}):
            data, _ = self.run_worker(worker)
        self.assertEqual(data["info"]["ext"], "mp4")
        video, _ = core.available_formats(data["info"])
        self.assertTrue(video, "Direct HTTP video must remain selectable when codec metadata is unknown")

    def test_actual_cli_separates_streams_and_emits_json_progress_and_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            info = {"id": "local-fixture", "title": "fixture", "extractor": "generic", "extractor_key": "Generic",
                    "webpage_url": self.url + "/video.mp4", "duration": 100,
                    "formats": [
                        {"format_id": "v1", "url": self.url + "/video.mp4", "ext": "mp4", "protocol": "http", "vcodec": "avc1", "acodec": "none", "filesize": len(self.files["/video.mp4"])},
                        {"format_id": "a1", "url": self.url + "/audio.m4a", "ext": "m4a", "protocol": "http", "vcodec": "none", "acodec": "mp4a", "filesize": len(self.files["/audio.m4a"])}]}
            fixture = Path(temp) / "fixture.json"
            fixture.write_text(json.dumps(info), encoding="utf-8")
            request = core.DownloadRequest(self.url + "/video.mp4", temp, mode="advanced",
                                           video_id="v1", audio_id="a1", merge=False)
            tools = {"yt-dlp": TEST_EXE}
            command = core.build_download_command(request, tools, info)
            command = command[:-2] + ["--load-info-json", str(fixture)]
            worker = TaskWorker("download", {"request": request, "info": info})
            with patch.object(core, "resolve_tools", return_value=tools), patch.object(core, "build_download_command", return_value=command):
                data, progress = self.run_worker(worker)
            self.assertEqual(len(data["files"]), 2)
            outputs = {Path(path).suffix: Path(path).read_bytes() for path in data["files"]}
            self.assertEqual(outputs[".mp4"], self.files["/video.mp4"])
            self.assertEqual(outputs[".m4a"], self.files["/audio.m4a"])
            self.assertTrue(any(0 <= percent < 100 for percent, text in progress))
            self.assertEqual(progress[-1][0], 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
