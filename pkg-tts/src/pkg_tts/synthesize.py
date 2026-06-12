from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class SynthesizedAudio:
    """角色語音合成結果（供 sub-character-voice 發布 character.audio.ready）。"""

    path: str
    duration_ms: int
    visemes: tuple[dict[str, Any], ...] = field(default_factory=tuple)


@runtime_checkable
class VoiceSynthesizer(Protocol):
    """角色語音合成抽象；與觀眾朗讀用的 TtsEngine.speak 分離。"""

    def synthesize(self, text: str, *, turn_id: str, language: str = "zh-TW") -> SynthesizedAudio:
        """將文字合成為音檔；turn_id 用於輸出路徑對齊。"""
