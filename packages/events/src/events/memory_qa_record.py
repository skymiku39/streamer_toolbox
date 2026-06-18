from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from events.topics import TOPIC_MEMORY_QA_RECORD

SCHEMA_VERSION = 1


@dataclass
class MemoryQaRecordEvent:
    schema_version: int
    topic: str
    timestamp: str
    channel: str
    platform: str
    correlation_id: str
    question: str
    reply: str
    memory_note: str
    memory_value: int
    store_worthy: bool
    ask_author: str = ""
    session_id: str | None = None
    category: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_MEMORY_QA_RECORD:
            raise ValueError(
                f"topic must be {TOPIC_MEMORY_QA_RECORD!r}, got {self.topic!r}"
            )
        if not self.timestamp:
            raise ValueError("timestamp is required")
        if not self.channel:
            raise ValueError("channel is required")
        if not self.platform:
            raise ValueError("platform is required")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")
        if not self.question.strip():
            raise ValueError("question is required")
        if not self.reply.strip():
            raise ValueError("reply is required")
        if not self.memory_note.strip():
            raise ValueError("memory_note is required")
        if self.memory_value < 0:
            raise ValueError("memory_value must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def build(
        cls,
        *,
        channel: str,
        platform: str,
        correlation_id: str,
        question: str,
        reply: str,
        memory_note: str,
        memory_value: int,
        store_worthy: bool,
        ask_author: str = "",
        session_id: str | None = None,
        category: str = "",
    ) -> MemoryQaRecordEvent:
        return cls(
            schema_version=SCHEMA_VERSION,
            topic=TOPIC_MEMORY_QA_RECORD,
            timestamp=datetime.now(UTC).isoformat(),
            channel=channel,
            platform=platform,
            correlation_id=correlation_id,
            question=question.strip(),
            reply=reply.strip(),
            memory_note=memory_note.strip(),
            memory_value=memory_value,
            store_worthy=store_worthy,
            ask_author=ask_author.strip(),
            session_id=session_id,
            category=category.strip(),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MemoryQaRecordEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            timestamp=payload["timestamp"],
            channel=payload["channel"],
            platform=payload["platform"],
            correlation_id=payload["correlation_id"],
            question=payload["question"],
            reply=payload["reply"],
            memory_note=payload["memory_note"],
            memory_value=int(payload["memory_value"]),
            store_worthy=bool(payload.get("store_worthy", True)),
            ask_author=str(payload.get("ask_author", "")),
            session_id=payload.get("session_id"),
            category=str(payload.get("category", "")),
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> MemoryQaRecordEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
