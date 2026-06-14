from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from events.topics import TOPIC_MEMORY_SUMMARY_READY

SCHEMA_VERSION = 1


@dataclass
class MemorySummaryReadyEvent:
    schema_version: int
    topic: str
    summary_id: int
    session_id: str
    source: str
    period_start: str
    period_end: str
    record_count: int
    created_at: str
    content: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_MEMORY_SUMMARY_READY:
            raise ValueError(
                f"topic must be {TOPIC_MEMORY_SUMMARY_READY!r}, got {self.topic!r}"
            )
        if not self.session_id:
            raise ValueError("session_id is required")
        if self.source not in {"chat", "stt", "qa"}:
            raise ValueError(f"unsupported source: {self.source}")
        if not self.period_start or not self.period_end:
            raise ValueError("period_start and period_end are required")
        if not self.created_at:
            raise ValueError("created_at is required")
        if not self.content:
            raise ValueError("content is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def build(
        cls,
        *,
        summary_id: int,
        session_id: str,
        source: str,
        period_start: str,
        period_end: str,
        record_count: int,
        content: str,
        created_at: str | None = None,
    ) -> MemorySummaryReadyEvent:
        return cls(
            schema_version=SCHEMA_VERSION,
            topic=TOPIC_MEMORY_SUMMARY_READY,
            summary_id=summary_id,
            session_id=session_id,
            source=source,
            period_start=period_start,
            period_end=period_end,
            record_count=record_count,
            created_at=created_at or datetime.now(UTC).isoformat(),
            content=content,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MemorySummaryReadyEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            summary_id=int(payload["summary_id"]),
            session_id=payload["session_id"],
            source=payload["source"],
            period_start=payload["period_start"],
            period_end=payload["period_end"],
            record_count=int(payload["record_count"]),
            created_at=payload["created_at"],
            content=payload["content"],
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> MemorySummaryReadyEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
