from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LlmSubscriberConfig:
    trigger_prefixes: list[str] = field(default_factory=lambda: ["!ask"])
    context_window_minutes: int = 5
    bot_reply_window_minutes: int = 30
    reply_max_length: int = 500
    input_blocklist: list[str] = field(default_factory=list)
    output_blocklist: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LlmSubscriberConfig:
        prefixes = data.get("trigger_prefixes", ["!ask"])
        if isinstance(prefixes, str):
            prefixes = [prefix.strip() for prefix in prefixes.split(",") if prefix.strip()]
        return cls(
            trigger_prefixes=list(prefixes),
            context_window_minutes=int(data.get("context_window_minutes", 5)),
            bot_reply_window_minutes=int(data.get("bot_reply_window_minutes", 30)),
            reply_max_length=int(data.get("reply_max_length", 500)),
            input_blocklist=list(data.get("input_blocklist", [])),
            output_blocklist=list(data.get("output_blocklist", [])),
        )

    @classmethod
    def load(cls, path: Path) -> LlmSubscriberConfig:
        with path.open(encoding="utf-8") as config_file:
            return cls.from_dict(json.load(config_file))

    @classmethod
    def from_env(cls) -> LlmSubscriberConfig:
        prefixes_raw = os.environ.get("LLM_TRIGGER_PREFIXES", "!ask")
        prefixes = [prefix.strip() for prefix in prefixes_raw.split(",") if prefix.strip()]
        return cls(
            trigger_prefixes=prefixes or ["!ask"],
            context_window_minutes=int(os.environ.get("LLM_CONTEXT_WINDOW_MINUTES", "15")),
            bot_reply_window_minutes=int(
                os.environ.get("LLM_BOT_REPLY_WINDOW_MINUTES", "30")
            ),
            reply_max_length=int(os.environ.get("LLM_MAX_REPLY_LENGTH", "500")),
            input_blocklist=[
                word.strip()
                for word in os.environ.get("LLM_INPUT_BLOCKLIST", "").split(",")
                if word.strip()
            ],
            output_blocklist=[
                word.strip()
                for word in os.environ.get("LLM_OUTPUT_BLOCKLIST", "").split(",")
                if word.strip()
            ],
        )
