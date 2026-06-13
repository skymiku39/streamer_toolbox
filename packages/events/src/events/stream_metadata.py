from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from events.topics import TOPIC_STREAM_METADATA

SCHEMA_VERSION = 1
PLATFORMS = frozenset({"youtube", "twitch", "discord"})


@dataclass
class StreamMetadataEvent:
    schema_version: int
    topic: str
    platform: str
    channel: str
    timestamp: str
    snapshot_id: str
    is_live: bool
    title: str = ""
    game_name: str = ""
    display_name: str = ""
    started_at: str = ""
    duration_seconds: int | None = None
    viewer_count: int | None = None
    stream_url: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_STREAM_METADATA:
            raise ValueError(f"topic must be {TOPIC_STREAM_METADATA!r}, got {self.topic!r}")
        if self.platform not in PLATFORMS:
            raise ValueError(f"unsupported platform: {self.platform}")
        if not self.channel:
            raise ValueError("channel is required")
        if not self.timestamp:
            raise ValueError("timestamp is required")
        if not self.snapshot_id:
            raise ValueError("snapshot_id is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StreamMetadataEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            platform=payload["platform"],
            channel=payload["channel"],
            timestamp=payload["timestamp"],
            snapshot_id=payload["snapshot_id"],
            is_live=bool(payload["is_live"]),
            title=str(payload.get("title", "") or ""),
            game_name=str(payload.get("game_name", "") or ""),
            display_name=str(payload.get("display_name", "") or ""),
            started_at=str(payload.get("started_at", "") or ""),
            duration_seconds=payload.get("duration_seconds"),
            viewer_count=payload.get("viewer_count"),
            stream_url=str(payload.get("stream_url", "") or ""),
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> StreamMetadataEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
