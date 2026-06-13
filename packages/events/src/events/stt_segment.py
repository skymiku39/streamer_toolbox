from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from events.topics import TOPIC_STT_SEGMENT

SCHEMA_VERSION = 1
PLATFORMS = frozenset({"youtube", "twitch", "discord"})


@dataclass
class SttSegmentEvent:
    schema_version: int
    topic: str
    platform: str
    channel: str
    segment_id: str
    text: str
    timestamp: str
    start_sec: float | None = None
    end_sec: float | None = None
    language: str | None = None
    confidence: float | None = None
    highlight_score: float | None = None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_STT_SEGMENT:
            raise ValueError(f"topic must be {TOPIC_STT_SEGMENT!r}, got {self.topic!r}")
        if self.platform not in PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.channel:
            raise ValueError("channel is required")
        if not self.segment_id:
            raise ValueError("segment_id is required")
        if not self.text:
            raise ValueError("text is required")
        if not self.timestamp:
            raise ValueError("timestamp is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SttSegmentEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            platform=payload["platform"],
            channel=payload["channel"],
            segment_id=payload["segment_id"],
            text=payload["text"],
            timestamp=payload["timestamp"],
            start_sec=payload.get("start_sec"),
            end_sec=payload.get("end_sec"),
            language=payload.get("language"),
            confidence=payload.get("confidence"),
            highlight_score=payload.get("highlight_score"),
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> SttSegmentEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
