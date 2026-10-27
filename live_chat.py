"""Convert yt-dlp YouTube live chat (.live_chat.json, one JSON object per line) to readable text."""
from datetime import datetime
import json
from pathlib import Path

CHAT_SUFFIX = ".live_chat.json"


def _text(value):
    if not isinstance(value, dict):
        return ""
    if "simpleText" in value:
        return str(value["simpleText"])
    parts = []
    for run in value.get("runs") or []:
        if "text" in run:
            parts.append(str(run["text"]))
        elif "emoji" in run:
            emoji = run["emoji"]
            # Unicode 表情的 emojiId 就是字元本身；頻道自訂表情使用 :shortcut: 文字。
            if emoji.get("isCustomEmoji") or not emoji.get("emojiId"):
                shortcuts = emoji.get("shortcuts") or []
                parts.append(shortcuts[0] if shortcuts else "□")
            else:
                parts.append(emoji["emojiId"])
    return "".join(parts)


def _offset(msec):
    msec = int(msec)
    sign = "-" if msec < 0 else ""
    seconds = abs(msec) // 1000
    return f"{sign}{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def _time(renderer, wrapper):
    if not wrapper.get("isLive") and wrapper.get("videoOffsetTimeMsec") is not None:
        try:
            return _offset(wrapper["videoOffsetTimeMsec"])
        except (TypeError, ValueError):
            pass
    # 直播進行中錄下的留言沒有影片時間軸，改用留言的實際時間。
    try:
        return datetime.fromtimestamp(int(renderer["timestampUsec"]) / 1e6).strftime("%Y-%m-%d %H:%M:%S")
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return _text(renderer.get("timestampText")) or "?"


def format_item(item, wrapper):
    """Return one readable line for a chat item, or None for non-message items."""
    if not isinstance(item, dict) or not item:
        return None
    kind, renderer = next(iter(item.items()))
    if not isinstance(renderer, dict):
        return None
    author = _text(renderer.get("authorName"))
    message = _text(renderer.get("message"))
    if kind == "liveChatTextMessageRenderer":
        tag = ""
    elif kind == "liveChatPaidMessageRenderer":
        tag = f"[Super Chat {_text(renderer.get('purchaseAmountText'))}] "
    elif kind == "liveChatPaidStickerRenderer":
        tag = f"[Super Sticker {_text(renderer.get('purchaseAmountText'))}] "
    elif kind == "liveChatMembershipItemRenderer":
        tag = "[會員] "
        header = _text(renderer.get("headerPrimaryText")) or _text(renderer.get("headerSubtext"))
        message = " ".join(part for part in (header, message) if part)
    elif kind == "liveChatSponsorshipsGiftPurchaseAnnouncementRenderer":
        header = (renderer.get("header") or {}).get("liveChatSponsorshipsHeaderRenderer") or {}
        tag = "[贈送會員] "
        author = _text(header.get("authorName"))
        message = _text(header.get("primaryText"))
    elif kind == "liveChatSponsorshipsGiftRedemptionAnnouncementRenderer":
        tag = "[獲贈會員] "
    else:
        return None
    line = f"[{_time(renderer, wrapper)}] {tag}{author or '（未知使用者）'}"
    return line + (f"：{message}" if message else "")


def convert_file(source, target=None, cancel_check=None):
    """Write a readable .txt next to the chat JSON; returns (target path, message count)."""
    source = Path(source)
    if target is None:
        name = source.name[:-len(CHAT_SUFFIX)] if source.name.endswith(CHAT_SUFFIX) else source.stem
        target = source.with_name(name + ".live_chat.txt")
    target = Path(target)
    count = 0
    temp = target.with_name(target.name + ".tmp")
    try:
        with source.open(encoding="utf-8", errors="replace") as lines, \
                temp.open("w", encoding="utf-8-sig", newline="\r\n") as output:
            output.write(f"# 聊天室紀錄：{source.name}\n")
            for number, raw in enumerate(lines):
                if cancel_check and number % 2000 == 0:
                    cancel_check()
                try:
                    wrapper = json.loads(raw)
                except ValueError:
                    continue  # 中斷錄製時最後一行可能不完整
                replay = wrapper.get("replayChatItemAction") if isinstance(wrapper, dict) else None
                if not isinstance(replay, dict):
                    continue
                for action in replay.get("actions") or []:
                    item = (action.get("addChatItemAction") or {}).get("item") if isinstance(action, dict) else None
                    line = format_item(item, {**replay, **wrapper})
                    if line:
                        output.write(line.replace("\r", " ").replace("\n", " ") + "\n")
                        count += 1
        temp.replace(target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return str(target), count
