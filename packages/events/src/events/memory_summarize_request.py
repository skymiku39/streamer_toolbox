from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from events.topics import TOPIC_MEMORY_SUMMARIZE_REQUEST

SCHEMA_VERSION = 1


@dataclass
class MemorySummarizeRequestEvent:
    schema_version: int
    topic: str
    timestamp: str
    session_id: str | None = None
    reason: str = "manual"
    source: str = "cli"

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_MEMORY_SUMMARIZE_REQUEST:
            raise ValueError(
                f"topic must be {TOPIC_MEMORY_SUMMARIZE_REQUEST!r}, got {self.topic!r}"
            )
        if not self.timestamp:
            raise ValueError("timestamp is required")
        if not self.reason:
            raise ValueError("reason is required")
        if not self.source:
            raise ValueError("source is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def build(
        cls,
        *,
        session_id: str | None = None,
        reason: str = "manual",
        source: str = "cli",
    ) -> MemorySummarizeRequestEvent:
        return cls(
            schema_version=SCHEMA_VERSION,
            topic=TOPIC_MEMORY_SUMMARIZE_REQUEST,
            timestamp=datetime.now(UTC).isoformat(),
            session_id=session_id,
            reason=reason,
            source=source,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MemorySummarizeRequestEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            timestamp=payload["timestamp"],
            session_id=payload.get("session_id"),
            reason=payload.get("reason", "manual"),
            source=payload.get("source", "cli"),
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> MemorySummarizeRequestEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
