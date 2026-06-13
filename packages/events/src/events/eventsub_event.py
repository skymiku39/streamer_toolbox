from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from events.topics import TOPIC_EVENTSUB_PREFIX

SCHEMA_VERSION = 1
PLATFORMS = frozenset({"youtube", "twitch", "discord"})

EVENTSUB_EVENT_TYPES = frozenset(
    {
        "follow",
        "raid",
        "subscribe",
        "subscription_gift",
        "subscription_message",
        "redemption",
        "bits",
        "stream_online",
        "stream_offline",
        "message_delete",
        "ban",
        "unban",
        "poll_begin",
        "poll_progress",
        "poll_end",
        "prediction_begin",
        "prediction_progress",
        "prediction_lock",
        "prediction_end",
        "hype_train_begin",
        "hype_train_progress",
        "hype_train_end",
        "automod_message_hold",
        "automod_message_update",
        "first_chat",
    }
)


def eventsub_topic(event_type: str) -> str:
    return f"{TOPIC_EVENTSUB_PREFIX}{event_type}"


@dataclass
class EventSubEvent:
    schema_version: int
    topic: str
    platform: str
    event_type: str
    broadcaster_id: str
    timestamp: str
    user_id: str | None = None
    user_name: str | None = None
    channel: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if not self.topic.startswith(TOPIC_EVENTSUB_PREFIX):
            raise ValueError(f"topic must start with {TOPIC_EVENTSUB_PREFIX!r}")
        if self.platform not in PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.event_type:
            raise ValueError("event_type is required")
        if self.event_type not in EVENTSUB_EVENT_TYPES:
            raise ValueError(f"unsupported event_type: {self.event_type}")
        expected_topic = eventsub_topic(self.event_type)
        if self.topic != expected_topic:
            raise ValueError(f"topic {self.topic!r} does not match event_type {self.event_type!r}")
        if not self.broadcaster_id:
            raise ValueError("broadcaster_id is required")
        if not self.timestamp:
            raise ValueError("timestamp is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EventSubEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            platform=payload["platform"],
            event_type=payload["event_type"],
            broadcaster_id=payload["broadcaster_id"],
            timestamp=payload["timestamp"],
            user_id=payload.get("user_id"),
            user_name=payload.get("user_name"),
            channel=payload.get("channel"),
            payload=payload.get("payload", {}),
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> EventSubEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
