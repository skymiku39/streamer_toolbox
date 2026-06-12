from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryWorkerConfig:
    db_path: str
    session_id: str | None
    interval_minutes: int
    llm_backend: str
    batch_limit: int
    record_mode: str

    @classmethod
    def from_env(cls) -> MemoryWorkerConfig:
        mode = (os.environ.get("RECORD_MODE", "chat") or "chat").strip().lower()
        return cls(
            db_path=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),
            session_id=(os.environ.get("STREAM_SESSION_ID") or "").strip() or None,
            interval_minutes=int(os.environ.get("MEMORY_INTERVAL_MINUTES", "5")),
            llm_backend=(os.environ.get("MEMORY_LLM_BACKEND", "template") or "template").lower(),
            batch_limit=int(os.environ.get("MEMORY_BATCH_LIMIT", "200")),
            record_mode=mode,
        )

    @property
    def include_chat(self) -> bool:
        return self.record_mode in {"chat", "both"}

    @property
    def include_stt(self) -> bool:
        return self.record_mode in {"stt", "both"}
