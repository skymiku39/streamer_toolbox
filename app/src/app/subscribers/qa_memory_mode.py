from __future__ import annotations

import os
from typing import Literal

QaMemoryMode = Literal["none", "structured", "batch"]
VALID_QA_MEMORY_MODES = frozenset({"none", "structured", "batch"})


def resolve_qa_memory_mode(raw: str | None = None) -> QaMemoryMode:
    """解析 Bot 問答長期記憶模式。

    - none：僅短期 buffer，不寫 RAG（原本行為）
    - structured：同次 LLM JSON 評分，高分寫入 RAG
    - batch：累積多次 chat.reply，交由 L2 定時摘要
    """
    if raw is None:
        raw = os.environ.get("QA_MEMORY_MODE", "")
        if not raw.strip():
            raw = _legacy_mode_from_env()
    mode = raw.strip().lower()
    if mode not in VALID_QA_MEMORY_MODES:
        known = ", ".join(sorted(VALID_QA_MEMORY_MODES))
        raise ValueError(f"unsupported QA_MEMORY_MODE: {raw!r}; expected one of: {known}")
    return mode  # type: ignore[return-value]


def _legacy_mode_from_env() -> str:
    batch = os.environ.get("QA_MEMORY_BATCH_ENABLED", "").strip().lower()
    if batch in {"1", "true", "yes", "on"}:
        return "batch"
    structured = os.environ.get("LLM_STRUCTURED_ASK", "").strip().lower()
    qa_enabled = os.environ.get("LLM_QA_MEMORY_ENABLED", "").strip().lower()
    if structured in {"1", "true", "yes", "on"} and qa_enabled not in {"0", "false", "no", "off"}:
        if qa_enabled in {"1", "true", "yes", "on"}:
            return "structured"
    structured_sub = os.environ.get("QA_MEMORY_STRUCTURED_ENABLED", "").strip().lower()
    if structured_sub in {"1", "true", "yes", "on"}:
        return "structured"
    return "none"


def structured_ask_enabled(mode: QaMemoryMode | None = None) -> bool:
    return resolve_qa_memory_mode(mode) == "structured"


def qa_memory_record_publish_enabled(mode: QaMemoryMode | None = None) -> bool:
    return resolve_qa_memory_mode(mode) == "structured"


def qa_memory_read_enabled(mode: QaMemoryMode | None = None) -> bool:
    """structured / batch 讀取 RAG 時含 source=qa；none 則排除問答長期記憶。"""
    return resolve_qa_memory_mode(mode) in {"structured", "batch"}
