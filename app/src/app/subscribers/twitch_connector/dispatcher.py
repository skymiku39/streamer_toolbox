"""依 platform 分派 chat.reply 至對應 Egress sender。"""

from __future__ import annotations

from typing import Protocol

from events import ChatReplyEvent


class ChatSender(Protocol):
    def send(
        self,
        channel: str,
        content: str,
        *,
        reply_to_message_id: str | None = None,
    ) -> None: ...


class UnsupportedPlatformError(ValueError):
    pass


class ChatReplyDispatcher:
    def __init__(self, senders: dict[str, ChatSender]) -> None:
        self._senders = senders

    def dispatch(self, event: ChatReplyEvent) -> None:
        sender = self._senders.get(event.platform)
        if sender is None:
            raise UnsupportedPlatformError(f"unsupported platform: {event.platform}")
        sender.send(
            event.channel,
            event.content,
            reply_to_message_id=event.reply_to_message_id,
        )
