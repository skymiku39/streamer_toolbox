from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from events.topics import TOPIC_CHARACTER_AUDIO_READY

SCHEMA_VERSION = 1


@dataclass
class CharacterAudioReadyEvent:
    schema_version: int
    topic: str
    turn_id: str
    audio_path: str
    duration_ms: int | None = None
    visemes: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_CHARACTER_AUDIO_READY:
            raise ValueError(
                f"topic must be {TOPIC_CHARACTER_AUDIO_READY!r}, got {self.topic!r}"
            )
        if not self.turn_id:
            raise ValueError("turn_id is required")
        if not self.audio_path:
            raise ValueError("audio_path is required")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CharacterAudioReadyEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            turn_id=payload["turn_id"],
            audio_path=payload["audio_path"],
            duration_ms=payload.get("duration_ms"),
            visemes=payload.get("visemes", []),
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> CharacterAudioReadyEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
