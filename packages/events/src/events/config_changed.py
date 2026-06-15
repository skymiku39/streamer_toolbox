from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from events.topics import TOPIC_CONFIG_CHANGED

SCHEMA_VERSION = 1


@dataclass
class ConfigChangedEvent:
    schema_version: int
    topic: str
    module_id: str
    profile_id: str
    config_file: str
    timestamp: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_CONFIG_CHANGED:
            raise ValueError(f"topic must be {TOPIC_CONFIG_CHANGED!r}, got {self.topic!r}")
        if not self.module_id:
            raise ValueError("module_id is required")
        if not self.profile_id:
            raise ValueError("profile_id is required")
        if not self.config_file:
            raise ValueError("config_file is required")
        if not self.timestamp:
            raise ValueError("timestamp is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def build(
        cls,
        *,
        module_id: str,
        config_file: str,
        profile_id: str = "default",
    ) -> ConfigChangedEvent:
        return cls(
            schema_version=SCHEMA_VERSION,
            topic=TOPIC_CONFIG_CHANGED,
            module_id=module_id,
            profile_id=profile_id,
            config_file=config_file,
            timestamp=datetime.now(UTC).isoformat(),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConfigChangedEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            module_id=payload["module_id"],
            profile_id=payload["profile_id"],
            config_file=payload["config_file"],
            timestamp=payload["timestamp"],
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> ConfigChangedEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
