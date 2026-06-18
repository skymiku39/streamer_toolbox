from __future__ import annotations

import sys
from typing import Any

from events import TOPIC_MEMORY_QA_RECORD, MemoryQaRecordEvent

from app.subscribers.stream_record_config import RecordConfig, resolve_session_id
from stream_store import StreamTextStore, set_active_session_for_channel
from stream_store.models import Summary


class StructuredQaMemoryWriter:
    """將 memory.qa.record 寫入 summaries(source=qa)。"""

    def __init__(self, store: StreamTextStore, config: RecordConfig) -> None:
        self._store = store
        self._config = config

    def handle(self, payload: dict[str, Any]) -> Summary | None:
        if payload.get("topic") != TOPIC_MEMORY_QA_RECORD:
            return None

        event = MemoryQaRecordEvent.from_dict(payload)
        channel = event.channel or "unknown"
        session_id = event.session_id or resolve_session_id(self._config, channel=channel)
        set_active_session_for_channel(self._store, channel=channel, session_id=session_id)

        content = event.memory_note.strip()
        if event.ask_author:
            content = f"{event.ask_author} 問：{event.question}\n{content}"

        summary = self._store.save_summary(
            session_id=session_id,
            period_start=event.timestamp,
            period_end=event.timestamp,
            source="qa",
            content=content,
            record_count=1,
            category=event.category,
        )
        print(
            f"[sub-qa-memory-structured] saved summary id={summary.id} "
            f"session={session_id} correlation={event.correlation_id[:8]}",
            file=sys.stderr,
            flush=True,
        )
        return summary
