from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MEMORY_INTERVAL_MINUTES = 30


@dataclass(frozen=True)
class MemoryWorkerConfig:
    db_path: str
    session_id: str | None
    channel: str | None
    interval_minutes: int
    llm_backend: str
    batch_limit: int
    record_mode: str
    merge_summary: bool = True

    @classmethod
    def from_env(cls) -> MemoryWorkerConfig:
        mode = (os.environ.get("RECORD_MODE", "chat") or "chat").strip().lower()
        channel = (
            os.environ.get("MEMORY_CHANNEL")
            or os.environ.get("TWITCH_CHANNEL")
            or ""
        ).strip() or None
        merge_raw = os.environ.get("MEMORY_MERGE_SUMMARY", "true").strip().lower()
        return cls(
            db_path=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),
            session_id=(os.environ.get("STREAM_SESSION_ID") or "").strip() or None,
            channel=channel,
            interval_minutes=int(
                os.environ.get("MEMORY_INTERVAL_MINUTES", str(DEFAULT_MEMORY_INTERVAL_MINUTES))
            ),
            llm_backend=(os.environ.get("MEMORY_LLM_BACKEND", "template") or "template").lower(),
            batch_limit=int(os.environ.get("MEMORY_BATCH_LIMIT", "200")),
            record_mode=mode,
            merge_summary=merge_raw in {"1", "true", "yes", "on"},
        )

    @property
    def include_chat(self) -> bool:
        return self.record_mode in {"chat", "both"}

    @property
    def include_stt(self) -> bool:
        return self.record_mode in {"stt", "both"}
