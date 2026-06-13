from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from events.topics import TOPIC_CHARACTER_TURN

SCHEMA_VERSION = 1
EMOTIONS = frozenset({"neutral", "happy", "angry", "sad", "surprised"})


@dataclass
class CharacterTurnEvent:
    schema_version: int
    topic: str
    turn_id: str
    correlation_id: str
    text: str
    emotion: str
    timestamp: str
    emotion_intensity: float = 1.0
    language: str = "zh-TW"

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_CHARACTER_TURN:
            raise ValueError(f"topic must be {TOPIC_CHARACTER_TURN!r}, got {self.topic!r}")
        if not self.turn_id:
            raise ValueError("turn_id is required")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")
        if not self.text:
            raise ValueError("text is required")
        if self.emotion not in EMOTIONS:
            raise ValueError(f"unsupported emotion: {self.emotion}")
        if not self.timestamp:
            raise ValueError("timestamp is required")
        if not 0.0 <= self.emotion_intensity <= 1.0:
            raise ValueError("emotion_intensity must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CharacterTurnEvent:
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            turn_id=payload["turn_id"],
            correlation_id=payload["correlation_id"],
            text=payload["text"],
            emotion=payload["emotion"],
            timestamp=payload["timestamp"],
            emotion_intensity=float(payload.get("emotion_intensity", 1.0)),
            language=payload.get("language", "zh-TW"),
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> CharacterTurnEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
