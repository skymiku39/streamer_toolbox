from __future__ import annotations

import os
import sys

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

# 會額外呼叫 LLM／grounding，POC 預設關閉
_HYBRID_TOKEN_CONSUMING_DEFAULTS: dict[str, str] = {
    "LLM_WEB_SEARCH": "false",
    "LLM_STARTUP_ANNOUNCEMENT": "false",
    "QA_MEMORY_MODE": "none",
}


def apply_hybrid_poc_env_defaults(*, knowledge_path: str | None = None) -> list[str]:
    """`LLM_BACKEND=hybrid` 時套用 POC 環境預設；回傳本次 setdefault 的鍵名。"""
    applied: list[str] = []
    for key, value in (
        *_HYBRID_ZERO_TOKEN_DEFAULTS.items(),
        *_HYBRID_TOKEN_CONSUMING_DEFAULTS.items(),
    ):
        if key not in os.environ:
            os.environ[key] = value
            applied.append(key)
    if knowledge_path and "LLM_KNOWLEDGE_PATH" not in os.environ:
        os.environ["LLM_KNOWLEDGE_PATH"] = knowledge_path
        applied.append("LLM_KNOWLEDGE_PATH")
    return applied


def hybrid_poc_feature_flags() -> dict[str, bool]:
    """回傳 hybrid POC 相關功能開關（供啟動 log）。"""

    def _on(name: str, default: bool = True) -> bool:
        raw = os.environ.get(name, "").strip().lower()
        if not raw:
            return default
        return raw in {"1", "true", "yes", "on"}

    return {
        "game_info": _on("LLM_GAME_INFO_ENABLED"),
        "session_recap": _on("LLM_SESSION_RECAP_ENABLED"),
        "l2_memory_rag": _on("LLM_MEMORY_FROM_DB"),
        "short_term_rag": _on("LLM_SHORT_TERM_RAG_ENABLED"),
        "static_kb": bool((os.environ.get("LLM_KNOWLEDGE_PATH") or "").strip()),
        "injection_guard": _on("LLM_INJECTION_GUARD"),
        "web_search": _on("LLM_WEB_SEARCH", False),
        "startup_announcement": _on("LLM_STARTUP_ANNOUNCEMENT", False),
    }


def log_hybrid_poc_startup(
    *,
    applied_defaults: list[str],
    flags: dict[str, bool],
) -> None:
    if applied_defaults:
        print(
            f"[sub-llm] hybrid POC setdefault: {', '.join(applied_defaults)}",
            file=sys.stderr,
            flush=True,
        )
    enabled = [name for name, on in flags.items() if on and name not in {"web_search", "startup_announcement"}]
    disabled = [name for name, on in flags.items() if not on and name in {"web_search", "startup_announcement"}]
    print(
        f"[sub-llm] hybrid POC enrichments={enabled!r} token_savers_off={disabled!r}",
        file=sys.stderr,
        flush=True,
    )
