"""GUI-independent validation, tool discovery and yt-dlp command construction."""
import math
import os
from pathlib import Path
import re
import shutil
import sys
from dataclasses import dataclass
from urllib.parse import urlsplit

VERSION = "1.2.0"
APP_DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "yt-dlp-gui"
PROJECT_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
YT_DLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
YT_DLP_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
MP4_FORMAT = "bv[ext=mp4][vcodec^=avc1]+ba[ext=m4a][acodec^=mp4a]/b[ext=mp4][vcodec^=avc1][acodec^=mp4a]"


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    folder: str
    name: str = ""
    mode: str = "mp4"
    video_id: str = ""
    audio_id: str = ""
    merge: bool = True
    playlist: bool = False
    clip: bool = False
    start: str = ""
    end: str = ""
    ffmpeg_dir: str = ""
    chat: bool = False
    chat_only: bool = False
    chat_text: bool = True


def validate_url(value, playlist=False):
    value = value.strip()
    if any(ord(c) < 32 for c in value):
        raise ValueError("網址不能包含換行或控制字元。")
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username
        parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("請輸入完整的 http:// 或 https:// 影片網址。")
    if not playlist and (parsed.hostname or "").lower() in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        if parsed.path.startswith(("/playlist", "/channel/", "/c/", "/user/", "/@")):
            raise ValueError("這是播放清單或頻道網址，請勾選「下載播放清單」。")
    return value


def validate_name(name):
    if not name:
        return
    if len(name) > 160 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name.endswith((".", " ")):
        raise ValueError("檔名不能含路徑或 Windows 不合法字元，也不能以空白或句點結尾（最多 160 字）。")
    if re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])", name.split(".")[0]):
        raise ValueError("這是 Windows 保留檔名，請換一個名稱。")


def parse_time(value):
    if not re.fullmatch(r"\d{1,3}:[0-5]\d:[0-5]\d(?:\.\d{1,3})?", value):
        raise ValueError("時間請使用 HH:MM:SS，例如 00:01:30；可附毫秒。")
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def validate_request(request, info=None):
    validate_url(request.url, request.playlist)
    if not Path(request.folder).is_dir():
        raise ValueError("下載資料夾不存在，請重新選擇。")
    if not os.access(request.folder, os.W_OK):
        raise ValueError("沒有下載資料夾的寫入權限。")
    validate_name(request.name)
    if request.mode not in ("mp4", "mp3", "m4a", "advanced"):
        raise ValueError("下載格式不正確。")
    if request.chat_only and not request.chat:
        raise ValueError("「只下載聊天室」需要先勾選「下載直播聊天室紀錄」。")
    if request.chat_only and request.clip:
        raise ValueError("聊天室紀錄只能完整下載，請改用全片下載。")
    if request.playlist and request.mode == "advanced" and not request.chat_only:
        raise ValueError("播放清單請使用簡單模式，避免各影片的格式 ID 不一致。")
    if request.mode == "advanced" and not request.chat_only:
        if not request.video_id and not request.audio_id:
            raise ValueError("請先取得格式清單，選擇影片或音訊格式。")
        for format_id in (request.video_id, request.audio_id):
            if format_id and not re.fullmatch(r"[A-Za-z0-9_.-]+", format_id):
                raise ValueError("格式 ID 不合法，請重新取得格式清單。")
        if info:
            ids = {str(item.get("format_id")) for item in info.get("formats", [])}
            if any(value and value not in ids for value in (request.video_id, request.audio_id)):
                raise ValueError("所選格式已失效，請重新取得格式清單。")
            video = next((f for f in info.get("formats", []) if str(f.get("format_id")) == request.video_id), {})
            if request.merge and request.audio_id and video.get("acodec") not in (None, "none"):
                raise ValueError("這個影片格式已含音訊；請移除另選的音訊，或選擇純影片格式。")
    if request.clip:
        if request.playlist:
            raise ValueError("片段下載目前只支援單支影片。")
        start = parse_time(request.start)
        end = parse_time(request.end) if request.end else math.inf
        if end <= start:
            raise ValueError("結束時間必須大於開始時間。")
        duration = (info or {}).get("duration")
        if duration and (start >= duration or (request.end and end > duration)):
            raise ValueError("片段時間超出影片長度。")


def resolve_tools(custom_ffmpeg=""):
    ytdlp = None
    for candidate in (APP_DATA_DIR / "yt-dlp.exe", PROJECT_DIR / "yt-dlp.exe"):
        if candidate.is_file():
            ytdlp = str(candidate)
            break
    ytdlp = ytdlp or shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    tools = {"yt-dlp": ytdlp, "ffmpeg": None, "ffprobe": None}
    if custom_ffmpeg:
        custom = Path(custom_ffmpeg)
        if not custom.is_dir():
            raise ValueError("自訂 FFmpeg 資料夾不存在。")
        for name in ("ffmpeg", "ffprobe"):
            candidate = custom / (name + ".exe")
            if not candidate.is_file():
                raise ValueError(f"自訂資料夾找不到 {name}.exe。")
            tools[name] = str(candidate)
    else:
        # yt-dlp 的 --ffmpeg-location 指向同一資料夾，必須找到完整工具組。
        search_dirs = [APP_DATA_DIR]
        for name in ("ffmpeg", "ffprobe"):
            path = shutil.which(name)
            if path:
                search_dirs.append(Path(path).parent)
        for directory in search_dirs:
            candidates = {name: directory / (name + (".exe" if os.name == "nt" else ""))
                          for name in ("ffmpeg", "ffprobe")}
            if all(path.is_file() for path in candidates.values()):
                tools.update({name: str(path) for name, path in candidates.items()})
                break
    return tools


def needs_ffmpeg(request):
    if request.chat_only:
        return False
    return (request.clip or request.mode in ("mp4", "mp3", "m4a")
            or (request.merge and bool(request.video_id and request.audio_id)))


def base_command(exe, playlist=False):
    return [exe, "--ignore-config", "--encoding", "utf-8", "--color", "never",
            "--yes-playlist" if playlist else "--no-playlist"]


def build_download_command(request, tools, info=None):
    validate_request(request, info)
    if not tools.get("yt-dlp"):
        raise ValueError("yt-dlp 未安裝，請先按「更新 yt-dlp」。")
    if needs_ffmpeg(request) and not (tools.get("ffmpeg") and tools.get("ffprobe")):
        raise ValueError("這個格式或片段下載需要 FFmpeg 與 FFprobe，請先安裝或指定工具資料夾。")
    cmd = base_command(tools["yt-dlp"], request.playlist)
    if not request.playlist:
        cmd += ["--playlist-items", "1"]
    separated = request.mode == "advanced" and not request.merge and not request.chat_only
    stem = request.name.replace("%", "%%") if request.name else "%(title)s [%(id)s]"
    if request.playlist:
        stem = "%(playlist_index)03d - " + stem
        if request.name:
            stem += " [%(id)s]"
    if separated:
        stem += ".f%(format_id)s"
    cmd += ["-o", str(Path(request.folder) / (stem + ".%(ext)s")),
            "--windows-filenames", "--newline", "--progress", "--no-simulate",
            "--progress-template", "download:GUI_PROGRESS:%(progress)j",
            "--progress-template", "postprocess:GUI_POST:%(progress)j",
            "--print", "before_dl:GUI_META:%(.{id,title,duration,requested_formats,filesize,filesize_approx})j",
            "--print", "after_move:GUI_FILE:%(filepath)j"]
    if tools.get("ffmpeg"):
        cmd += ["--ffmpeg-location", str(Path(tools["ffmpeg"]).parent)]
    if request.chat:
        # YouTube 直播／首播的聊天室在 yt-dlp 中是名為 live_chat 的字幕軌。
        cmd += ["--write-subs", "--sub-langs", "live_chat"]
    if request.chat_only:
        cmd += ["--skip-download"]
    elif request.mode == "mp4":
        cmd += ["-f", MP4_FORMAT, "--merge-output-format", "mp4", "--remux-video", "mp4"]
    elif request.mode in ("mp3", "m4a"):
        cmd += ["-f", "ba/b", "-x", "--audio-format", request.mode]
    else:
        selected = [value for value in (request.video_id, request.audio_id) if value]
        cmd += ["-f", ("," if separated else "+").join(selected)]
    if request.clip and not request.chat_only:
        cmd += ["--download-sections", f"*{request.start}-{request.end or 'inf'}"]
    cmd += ["--", request.url.strip()]
    return cmd


def available_formats(info):
    video, audio = [], []
    for item in info.get("formats") or []:
        if item.get("has_drm") or not item.get("format_id"):
            continue
        unknown_video = (item.get("vcodec") is None and item.get("acodec") in (None, "none")
                         and item.get("ext") in ("mp4", "webm", "mkv", "mov", "flv", "avi", "m4v"))
        if item.get("vcodec") not in (None, "none") or unknown_video:
            video.append(item)
        elif item.get("acodec") not in (None, "none") or item.get("ext") in ("m4a", "mp3", "aac", "opus", "ogg", "wav", "flac"):
            audio.append(item)
    video.sort(key=lambda f: (f.get("height") or 0, f.get("fps") or 0, f.get("tbr") or 0), reverse=True)
    audio.sort(key=lambda f: f.get("abr") or f.get("tbr") or 0, reverse=True)
    return video, audio


def format_size(size):
    if not size or not math.isfinite(float(size)):
        return "大小未知"
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024


def estimate_size(request, info):
    if request.chat_only:
        return "只下載聊天室：大小依留言數量而定"
    if not info or request.playlist:
        return "大小待取得影片資訊" if not request.playlist else "播放清單：各影片分別顯示進度"
    video, audio = available_formats(info)
    selected = []
    if request.mode == "advanced":
        ids = {request.video_id, request.audio_id} - {""}
        selected = [f for f in info.get("formats", []) if str(f.get("format_id")) in ids]
    elif request.mode == "mp4":
        videos = [f for f in video if f.get("ext") == "mp4" and str(f.get("vcodec", "")).startswith("avc1")]
        audios = [f for f in audio if f.get("ext") == "m4a" and str(f.get("acodec", "")).startswith("mp4a")]
        video_only = [f for f in videos if f.get("acodec") in (None, "none")]
        combined = [f for f in videos if str(f.get("acodec", "")).startswith("mp4a")]
        selected = [video_only[0], audios[0]] if video_only and audios else combined[:1]
    else:
        selected = audio[:1] or video[:1]
    sizes = [f.get("filesize") or f.get("filesize_approx") for f in selected]
    if not sizes or any(not size for size in sizes):
        return "所選格式大小未知"
    size = sum(sizes)
    suffix = "（來源檔案估算）"
    if request.clip and info.get("duration"):
        try:
            start = parse_time(request.start)
            end = parse_time(request.end) if request.end else info["duration"]
            size *= max(0, min(end, info["duration"]) - start) / info["duration"]
            suffix = "（片段粗估；實際大小可能不同）"
        except ValueError:
            return "請先填寫有效的片段時間"
    return f"約 {format_size(size)}{suffix}"
