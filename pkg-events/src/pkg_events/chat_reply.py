from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from pkg_events.topics import REPLY_SOURCES, TOPIC_CHAT_REPLY

SCHEMA_VERSION = 1
PLATFORMS = frozenset({"youtube", "twitch", "discord"})
SENDERS = frozenset({"bot", "character"})


@dataclass
class ChatReplyEvent:
    schema_version: int
    topic: str
    platform: str
    channel: str
    content: str
    reply_to_message_id: str | None = None
    sender: str = "bot"
    source: str = "logic-llm"
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_CHAT_REPLY:
            raise ValueError(f"topic must be {TOPIC_CHAT_REPLY!r}, got {self.topic!r}")
        if self.platform not in PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.channel:
            raise ValueError("channel is required")
        if not self.content:
            raise ValueError("content is required")
        if self.sender not in SENDERS:
            raise ValueError(f"unsupported sender: {self.sender}")
        if self.source not in REPLY_SOURCES:
            raise ValueError(f"unsupported source: {self.source}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ChatReplyEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            platform=payload["platform"],
            channel=payload["channel"],
            content=payload["content"],
            reply_to_message_id=payload.get("reply_to_message_id"),
            sender=payload.get("sender", "bot"),
            source=payload.get("source", "logic-llm"),
            correlation_id=payload.get("correlation_id"),
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> ChatReplyEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
