from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.subscribers.qa_memory_mode import QaMemoryMode, resolve_qa_memory_mode

DEFAULT_REPLY_MAX_LENGTH = 200
TWITCH_CHAT_MAX_CHARS = 500


def resolve_reply_max_length() -> int:
    """Prompt 組裝用的回覆正文上限（與 LlmSubscriberConfig 預設一致）。"""
    return int(
        os.environ.get("LLM_MAX_REPLY_LENGTH", str(DEFAULT_REPLY_MAX_LENGTH))
    )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass
class LlmSubscriberConfig:
    trigger_prefixes: list[str] = field(default_factory=lambda: ["!ask"])
    context_window_minutes: int = 5
    bot_reply_window_minutes: int = 30
    bot_reply_max_pairs: int = 5
    reply_max_length: int = DEFAULT_REPLY_MAX_LENGTH
    qa_memory_mode: QaMemoryMode = "none"
    qa_memory_min_value: int = 3
    input_blocklist: list[str] = field(default_factory=list)
    output_blocklist: list[str] = field(default_factory=list)

    @property
    def structured_ask_enabled(self) -> bool:
        return self.qa_memory_mode == "structured"

    @property
    def qa_memory_enabled(self) -> bool:
        return self.qa_memory_mode == "structured"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LlmSubscriberConfig:
        prefixes = data.get("trigger_prefixes", ["!ask"])
        if isinstance(prefixes, str):
            prefixes = [prefix.strip() for prefix in prefixes.split(",") if prefix.strip()]
        mode_raw = data.get("qa_memory_mode")
        if mode_raw is None and data.get("structured_ask_enabled") is True:
            mode_raw = "structured"
        qa_memory_mode = (
            resolve_qa_memory_mode() if mode_raw is None else resolve_qa_memory_mode(str(mode_raw))
        )
        return cls(
            trigger_prefixes=list(prefixes),
            context_window_minutes=int(data.get("context_window_minutes", 5)),
            bot_reply_window_minutes=int(data.get("bot_reply_window_minutes", 30)),
            bot_reply_max_pairs=int(data.get("bot_reply_max_pairs", 5)),
            reply_max_length=int(
                data.get("reply_max_length", DEFAULT_REPLY_MAX_LENGTH)
            ),
            qa_memory_mode=qa_memory_mode,
            qa_memory_min_value=int(data.get("qa_memory_min_value", 3)),
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
            bot_reply_max_pairs=int(os.environ.get("LLM_BOT_REPLY_MAX_PAIRS", "5")),
            reply_max_length=int(
                os.environ.get("LLM_MAX_REPLY_LENGTH", str(DEFAULT_REPLY_MAX_LENGTH))
            ),
            qa_memory_mode=resolve_qa_memory_mode(),
            qa_memory_min_value=int(os.environ.get("LLM_QA_MEMORY_MIN_VALUE", "3")),
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
