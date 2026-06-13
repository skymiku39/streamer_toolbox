from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from pkg_events.topics import TOPIC_SYSTEM_ERROR

SCHEMA_VERSION = 1


@dataclass
class SystemErrorEvent:
    schema_version: int
    topic: str
    component: str
    message: str
    timestamp: str
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_SYSTEM_ERROR:
            raise ValueError(f"topic must be {TOPIC_SYSTEM_ERROR!r}, got {self.topic!r}")
        if not self.component:
            raise ValueError("component is required")
        if not self.message:
            raise ValueError("message is required")
        if not self.timestamp:
            raise ValueError("timestamp is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SystemErrorEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            component=payload["component"],
            message=payload["message"],
            timestamp=payload["timestamp"],
            detail=payload.get("detail", {}),
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> SystemErrorEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
