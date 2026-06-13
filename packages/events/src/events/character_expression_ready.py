from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from events.topics import TOPIC_CHARACTER_EXPRESSION_READY

SCHEMA_VERSION = 1
DRIVERS = frozenset({"vts"})


@dataclass
class CharacterExpressionReadyEvent:
    schema_version: int
    topic: str
    turn_id: str
    driver: str
    parameters: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.topic != TOPIC_CHARACTER_EXPRESSION_READY:
            raise ValueError(
                f"topic must be {TOPIC_CHARACTER_EXPRESSION_READY!r}, got {self.topic!r}"
            )
        if not self.turn_id:
            raise ValueError("turn_id is required")
        if self.driver not in DRIVERS:
            raise ValueError(f"unsupported driver: {self.driver}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CharacterExpressionReadyEvent:
        raw_params = payload.get("parameters", {})
        parameters = {key: float(value) for key, value in raw_params.items()}
        return cls(
            schema_version=payload["schema_version"],
            topic=payload["topic"],
            turn_id=payload["turn_id"],
            driver=payload["driver"],
            parameters=parameters,
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> CharacterExpressionReadyEvent:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_dict(json.loads(data))
