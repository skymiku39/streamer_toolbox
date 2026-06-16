from __future__ import annotations

import os
import sys

from app.subscribers.qa_memory_mode import qa_memory_read_enabled, resolve_qa_memory_mode

# hybrid POC：僅在未於 .env 明確設定時套用（setdefault，不覆寫使用者意圖）

# 不消耗 LLM token，僅檢索／規則／外部 REST（IGDB）
_HYBRID_ZERO_TOKEN_DEFAULTS: dict[str, str] = {
    "LLM_GAME_INFO_ENABLED": "true",
    "LLM_SESSION_RECAP_ENABLED": "true",
    "LLM_MEMORY_FROM_DB": "true",
    "LLM_SHORT_TERM_RAG_ENABLED": "true",
    "LLM_INJECTION_GUARD": "true",
    "LLM_KNOWLEDGE_BACKEND": "chroma",
}

# 低頻／低 token：batch 寫入僅落 SQLite；L2 摘要由 memory worker 定時執行（非每次 ask）
_HYBRID_LOW_TOKEN_DEFAULTS: dict[str, str] = {
    "QA_MEMORY_MODE": "batch",
}

# 會額外呼叫 LLM／grounding，POC 預設關閉
_HYBRID_TOKEN_CONSUMING_DEFAULTS: dict[str, str] = {
    "LLM_WEB_SEARCH": "false",
    "LLM_STARTUP_ANNOUNCEMENT": "false",
}


def apply_hybrid_poc_env_defaults(*, knowledge_path: str | None = None) -> list[str]:
    """`LLM_BACKEND=hybrid` 時套用 POC 環境預設；回傳本次 setdefault 的鍵名。"""
    applied: list[str] = []
    for key, value in (
        *_HYBRID_ZERO_TOKEN_DEFAULTS.items(),
        *_HYBRID_LOW_TOKEN_DEFAULTS.items(),
        *_HYBRID_TOKEN_CONSUMING_DEFAULTS.items(),
    ):
        if key not in os.environ:
            os.environ[key] = value
            applied.append(key)
    if knowledge_path and "LLM_KNOWLEDGE_PATH" not in os.environ:
        os.environ["LLM_KNOWLEDGE_PATH"] = knowledge_path
        applied.append("LLM_KNOWLEDGE_PATH")
    return applied


def hybrid_poc_feature_flags() -> dict[str, bool | str]:
    """回傳 hybrid POC 相關功能開關（供啟動 log）。"""

    def _on(name: str, default: bool = True) -> bool:
        raw = os.environ.get(name, "").strip().lower()
        if not raw:
            return default
        return raw in {"1", "true", "yes", "on"}

    qa_mode = resolve_qa_memory_mode()
    return {
        "game_info": _on("LLM_GAME_INFO_ENABLED"),
        "session_recap": _on("LLM_SESSION_RECAP_ENABLED"),
        "l2_memory_rag": _on("LLM_MEMORY_FROM_DB"),
        "qa_memory_read": qa_memory_read_enabled(qa_mode),
        "qa_memory_mode": qa_mode,
        "short_term_rag": _on("LLM_SHORT_TERM_RAG_ENABLED"),
        "static_kb": bool((os.environ.get("LLM_KNOWLEDGE_PATH") or "").strip()),
        "injection_guard": _on("LLM_INJECTION_GUARD"),
        "web_search": _on("LLM_WEB_SEARCH", False),
        "startup_announcement": _on("LLM_STARTUP_ANNOUNCEMENT", False),
    }


def log_hybrid_poc_startup(
    *,
    applied_defaults: list[str],
    flags: dict[str, bool | str],
) -> None:
    if applied_defaults:
        print(
            f"[sub-llm] hybrid POC setdefault: {', '.join(applied_defaults)}",
            file=sys.stderr,
            flush=True,
        )
    skip = {"web_search", "startup_announcement", "qa_memory_mode"}
    enabled = [name for name, on in flags.items() if on is True and name not in skip]
    disabled = [
        name
        for name, on in flags.items()
        if on is False and name in {"web_search", "startup_announcement"}
    ]
    qa_mode = flags.get("qa_memory_mode", "none")
    print(
        f"[sub-llm] hybrid POC enrichments={enabled!r} "
        f"qa_memory_mode={qa_mode!r} token_savers_off={disabled!r}",
        file=sys.stderr,
        flush=True,
    )
    if qa_mode == "batch":
        print(
            "[sub-llm] hybrid POC: QA 長期記憶 batch 已啟用；"
            "L2 摘要需另跑 app.workers（定時、低頻 token）",
            file=sys.stderr,
            flush=True,
        )
