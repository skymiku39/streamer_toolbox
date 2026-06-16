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
