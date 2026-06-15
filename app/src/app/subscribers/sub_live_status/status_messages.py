from __future__ import annotations

import os

from events import StreamMetadataEvent


def live_status_announcement_enabled() -> bool:
    raw = os.environ.get("LIVE_STATUS_ANNOUNCEMENT", "true").strip().lower()
    if not raw:
        return True
    return raw in {"1", "true", "yes", "on"}


def resolve_status_channel() -> str:
    return (os.environ.get("TWITCH_CHANNEL") or "").strip().lstrip("#")


def _format_duration(seconds: int | None) -> str:
    if seconds is None or seconds < 0:
        return ""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} 小時 {minutes} 分"
    if minutes:
        return f"{minutes} 分 {secs} 秒"
    return f"{secs} 秒"


def build_live_status_message(event: StreamMetadataEvent) -> str:
    """依 stream.metadata 組裝可發送至聊天室的狀態宣告（模板，不經 LLM）。"""
    channel = (event.channel or resolve_status_channel()).strip().lstrip("#")
    if event.is_live:
        status = "直播中"
        duration = _format_duration(event.duration_seconds)
        duration_part = f"，已開播 {duration}" if duration else ""
    else:
        status = "離線"
        duration_part = ""

    title = (event.title or "").strip() or "（無標題）"
    game = (event.game_name or "").strip() or "（未設定分類）"

    return (
        f"【系統狀態】{channel} 擷取服務已連線。"
        f"目前{status}：「{title}」｜{game}{duration_part}。"
        f"問答模式未啟用，僅記錄聊天與語音。"
    )
