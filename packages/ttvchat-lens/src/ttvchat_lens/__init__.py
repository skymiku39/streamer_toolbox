"""TTVChat Lens: Twitch 直播聊天室讀取工具。"""

from __future__ import annotations

from .reader import ChatMessage, LiveChatReader, channel_url, parse_twitch_channel

__all__ = [
    "ChatMessage",
    "LiveChatReader",
    "parse_twitch_channel",
    "channel_url",
    "main",
]


def main() -> None:
    """CLI 進入點，將參數轉交給 ttvchat_lens.cli。"""
    from .cli import run

    run()
