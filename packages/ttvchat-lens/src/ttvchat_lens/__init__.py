"""TTVChat Lens: Twitch 直播聊天室讀取工具。"""

from __future__ import annotations

from .reader import ChatMessage, LiveChatReader, channel_url, normalize_channel

__all__ = [
    "ChatMessage",
    "LiveChatReader",
    "normalize_channel",
    "channel_url",
    "main",
]


def main() -> None:
    """CLI 進入點，將參數轉交給 ttvchat_lens.cli。"""
    from .cli import run

    run()
