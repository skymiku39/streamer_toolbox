from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from events.topics import TOPIC_CHAT_MESSAGE

SCHEMA_VERSION = 1
PLATFORMS = frozenset({"youtube", "twitch", "discord"})


@dataclass
class ChatMessageEvent:
    schema_version: int
    topic: str
    platform: str
    message_id: str
    author_name: str
    content: str
    timestamp: str
    login: str | None = None
    author_id: str | None = None
    channel: str | None = None
    badges: list[Any] = field(default_factory=list)
    emote_url_map: dict[str, str] = field(default_factory=dict)
    reply: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_CHAT_MESSAGE:
            raise ValueError(f"topic must be {TOPIC_CHAT_MESSAGE!r}, got {self.topic!r}")
        if self.platform not in PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.message_id:
            raise ValueError("message_id is required")
        if not self.author_name:
            raise ValueError("author_name is required")
        if not self.content:
            raise ValueError("content is required")
        if not self.timestamp:
            raise ValueError("timestamp is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ChatMessageEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            platform=payload["platform"],
            message_id=payload["message_id"],
            author_name=payload["author_name"],
            content=payload["content"],
            timestamp=payload["timestamp"],
            login=payload.get("login"),
            author_id=payload.get("author_id"),
            channel=payload.get("channel"),
            badges=payload.get("badges", []),
            emote_url_map=payload.get("emote_url_map", {}),
            reply=payload.get("reply"),
            raw=payload.get("raw", {}),
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> ChatMessageEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
