from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    start_sec: float
    end_sec: float
    confidence: float = 0.0
