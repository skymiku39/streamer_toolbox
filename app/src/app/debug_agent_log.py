from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_DEBUG_LOG = Path(os.environ.get("DEBUG_LOG_PATH", "debug-7e40df.log")).expanduser()
if not _DEBUG_LOG.is_absolute():
    _DEBUG_LOG = (Path.cwd() / _DEBUG_LOG).resolve()
_SESSION_ID = "7e40df"


def agent_debug_log(
    location: str,
    message: str,
    data: dict[str, Any],
    *,
    hypothesis_id: str,
    run_id: str = "pre-fix",
) -> None:
    # #region agent log
    try:
        entry = {
            "sessionId": _SESSION_ID,
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data,
            "hypothesisId": hypothesis_id,
            "runId": run_id,
            "pid": os.getpid(),
        }
        with _DEBUG_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
    # #endregion
