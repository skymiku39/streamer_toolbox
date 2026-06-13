from __future__ import annotations

from dataclasses import dataclass

from events import CharacterAudioReadyEvent, CharacterExpressionReadyEvent


@dataclass(frozen=True)
class StageCue:
    turn_id: str
    audio: CharacterAudioReadyEvent
    expression: CharacterExpressionReadyEvent | None
    expression_fallback: bool = False
