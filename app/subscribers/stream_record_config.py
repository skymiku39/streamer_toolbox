from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class RecordConfig:
    db_path: str
    session_id: str | None
    record_mode: str

    @classmethod
    def from_env(cls) -> RecordConfig:
        mode = (os.environ.get("RECORD_MODE", "chat") or "chat").strip().lower()
        return cls(
            db_path=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),
            session_id=(os.environ.get("STREAM_SESSION_ID") or "").strip() or None,
            record_mode=mode,
        )

    def validate(self) -> None:
        if self.record_mode not in {"chat", "stt", "both"}:
            raise ValueError(f"unsupported RECORD_MODE: {self.record_mode!r}")
        if self.record_mode != "chat":
            raise ValueError(
                "Phase 1 only supports RECORD_MODE=chat; stt/both will come in a later phase"
            )


def resolve_session_id(config: RecordConfig, *, channel: str) -> str:
    if config.session_id:
        return config.session_id
    day = datetime.now(UTC).strftime("%Y%m%d")
    normalized = channel.lstrip("#").lower() or "unknown"
    return f"{normalized}_{day}"
