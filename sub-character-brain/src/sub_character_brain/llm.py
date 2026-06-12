from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sub_character_brain.config import CharacterConfig

EMOTION_KEYWORDS: dict[str, tuple[str, float]] = {
    "開心": ("happy", 0.85),
    "高興": ("happy", 0.85),
    "快樂": ("happy", 0.8),
    "生氣": ("angry", 0.9),
    "憤怒": ("angry", 0.9),
    "難過": ("sad", 0.8),
    "傷心": ("sad", 0.8),
    "害怕": ("sad", 0.75),
    "驚訝": ("surprised", 0.8),
    "驚喜": ("surprised", 0.75),
}


@dataclass(frozen=True)
class CharacterResponse:
    text: str
    emotion: str
    emotion_intensity: float


@dataclass(frozen=True)
class MemoryTurn:
    author_name: str
    user_text: str
    character_text: str


class CharacterLlm(Protocol):
    def generate(
        self,
        *,
        config: CharacterConfig,
        author_name: str,
        user_text: str,
        memory: list[MemoryTurn],
    ) -> CharacterResponse:
        """依人設與記憶產出角色回應。"""


class RuleBasedCharacterLlm:
    """規則引擎佔位實作；未連接外部 LLM API。"""

    def generate(
        self,
        *,
        config: CharacterConfig,
        author_name: str,
        user_text: str,
        memory: list[MemoryTurn],
    ) -> CharacterResponse:
        emotion, intensity = self._detect_emotion(user_text, config)
        memory_hint = ""
        if memory:
            last = memory[-1]
            memory_hint = f"（我記得剛才跟 {last.author_name} 聊過天）"

        if user_text:
            text = (
                f"{config.character_name}：哈囉 {author_name}！"
                f"{user_text}{memory_hint}"
            )
        else:
            text = f"{config.character_name}：哈囉 {author_name}！有什麼想聊的嗎？{memory_hint}"

        return CharacterResponse(
            text=text,
            emotion=emotion,
            emotion_intensity=intensity,
        )

    def _detect_emotion(
        self,
        user_text: str,
        config: CharacterConfig,
    ) -> tuple[str, float]:
        for keyword, (emotion, intensity) in EMOTION_KEYWORDS.items():
            if keyword in user_text:
                return emotion, intensity
        return config.default_emotion, config.default_emotion_intensity
