from __future__ import annotations

import json
import os
import sys
from typing import Any

_LOG_PREFIX = "[sub-llm]"


def _json_enabled() -> bool:
    return os.environ.get("LLM_LOG_JSON", "").strip().lower() in {"1", "true", "yes", "on"}


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str) and (value == "" or any(ch.isspace() for ch in value)):
        return repr(value)
    return str(value)


def log_event(event: str, **fields: Any) -> None:
    """輸出單行結構化決策紀錄；`LLM_LOG_JSON=true` 時改為 JSON 便於彙整。"""
    payload: dict[str, Any] = {"event": event}
    payload.update({key: value for key, value in fields.items() if value is not None})
    if _json_enabled():
        line = f"{_LOG_PREFIX} {json.dumps(payload, ensure_ascii=False)}"
    else:
        rendered = " ".join(f"{key}={_format_value(value)}" for key, value in payload.items())
        line = f"{_LOG_PREFIX} {rendered}"
    print(line, file=sys.stderr, flush=True)


def _prompt_log_disabled() -> bool:
    return os.environ.get("LLM_LOG_PROMPT", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }


def _prompt_log_max_chars() -> int | None:
    raw = os.environ.get("LLM_LOG_PROMPT_MAX_CHARS", "").strip()
    if not raw:
        return None
    try:
        limit = int(raw)
    except ValueError:
        return None
    return None if limit <= 0 else limit


def _truncate_prompt_text(text: str, max_chars: int | None) -> str:
    if max_chars is None or len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n...(truncated, total {len(text)} chars)"


def log_llm_messages(messages: list[dict[str, str]], *, purpose: str) -> None:
    """記錄送給 LLM 的 messages；預設開啟，可用 `LLM_LOG_PROMPT=0` 關閉。"""
    if _prompt_log_disabled():
        return
    max_chars = _prompt_log_max_chars()
    rendered_messages = [
        {
            "role": str(message.get("role", "?")),
            "content": _truncate_prompt_text(str(message.get("content", "")), max_chars),
        }
        for message in messages
    ]
    if _json_enabled():
        payload = {
            "event": "llm_prompt",
            "purpose": purpose,
            "messages": rendered_messages,
        }
        print(
            f"{_LOG_PREFIX} {json.dumps(payload, ensure_ascii=False)}",
            file=sys.stderr,
            flush=True,
        )
        return
    print(f"{_LOG_PREFIX} llm_prompt purpose={purpose}", file=sys.stderr, flush=True)
    for message in rendered_messages:
        print(f"[{message['role']}]", file=sys.stderr, flush=True)
        print(message["content"], file=sys.stderr, flush=True)
    print(f"{_LOG_PREFIX} llm_prompt end purpose={purpose}", file=sys.stderr, flush=True)
