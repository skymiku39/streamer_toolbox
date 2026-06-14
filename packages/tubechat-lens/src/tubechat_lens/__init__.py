"""TubeChat Lens: YouTube 直播聊天室讀取工具。"""

from __future__ import annotations

from .reader import ChatMessage, LiveChatReader, normalize_video_url

__all__ = [
    "ChatMessage",
    "LiveChatReader",
    "normalize_video_url",
    "main",
]


def main() -> None:
    """CLI 進入點，將參數轉交給 tubechat_lens.cli。"""
    from .cli import run

    run()
