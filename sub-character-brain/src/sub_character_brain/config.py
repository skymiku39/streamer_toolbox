from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CharacterConfig:
    character_name: str = "Miko"
    persona_prompt: str = "你是一位活潑的虛擬主播助手。"
    trigger_prefix: str = "!talk"
    respond_to_all: bool = False
    language: str = "zh-TW"
    default_emotion: str = "neutral"
    default_emotion_intensity: float = 0.5
    publish_chat_reply: bool = True
    chat_reply_max_length: int = 200
    memory_max_turns: int = 10
    input_blocklist: list[str] = field(default_factory=list)
    output_blocklist: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CharacterConfig:
        return cls(
            character_name=data.get("character_name", cls.character_name),
            persona_prompt=data.get("persona_prompt", cls.persona_prompt),
            trigger_prefix=data.get("trigger_prefix", cls.trigger_prefix),
            respond_to_all=bool(data.get("respond_to_all", cls.respond_to_all)),
            language=data.get("language", cls.language),
            default_emotion=data.get("default_emotion", cls.default_emotion),
            default_emotion_intensity=float(
                data.get("default_emotion_intensity", cls.default_emotion_intensity)
            ),
            publish_chat_reply=bool(data.get("publish_chat_reply", cls.publish_chat_reply)),
            chat_reply_max_length=int(
                data.get("chat_reply_max_length", cls.chat_reply_max_length)
            ),
            memory_max_turns=int(data.get("memory_max_turns", cls.memory_max_turns)),
            input_blocklist=list(data.get("input_blocklist", [])),
            output_blocklist=list(data.get("output_blocklist", [])),
        )

    @classmethod
    def load(cls, path: Path) -> CharacterConfig:
        with path.open(encoding="utf-8") as config_file:
            return cls.from_dict(json.load(config_file))
