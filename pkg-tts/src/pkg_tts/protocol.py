from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class AudioClip:
    """合成音訊片段（供需檔案輸出的實作使用）。"""

    data: bytes
    mime_type: str = "audio/wav"


@runtime_checkable
class TtsEngine(Protocol):
    """TTS 引擎抽象；實作可互換（SAPI5、雲端、NoOp 等）。"""

    def speak(self, text: str) -> None:
        """朗讀文字；阻塞直到播放完成或引擎內部佇列清空。"""
