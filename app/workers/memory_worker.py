from __future__ import annotations

import sys

from pkg_stream_store import ACTIVE_SESSION_KEY, StreamTextStore
from pkg_stream_store.models import TextRecord

from app.workers.memory_config import MemoryWorkerConfig
from app.workers.memory_summarizer import Summarizer


class MemoryWorker:
    def __init__(
        self,
        store: StreamTextStore,
        config: MemoryWorkerConfig,
        summarizer: Summarizer,
    ) -> None:
        self._store = store
        self._config = config
        self._summarizer = summarizer

    def run_once(self) -> int:
        session_id = self._resolve_session_id()
        if session_id is None:
            print("[memory-worker] no session yet; waiting for chat records", file=sys.stderr)
            return 0

        records = self._store.fetch_unsummarized_chat(
            session_id,
            limit=self._config.batch_limit,
        )
        if not records:
            return 0

        content = self._summarizer.summarize_chat(records)
        period_start = records[0].timestamp
        period_end = records[-1].timestamp
        summary_id = self._store.save_summary(
            session_id=session_id,
            period_start=period_start,
            period_end=period_end,
            source="chat",
            content=content,
            record_count=len(records),
        )
        self._store.mark_summarized([record.id for record in records])
        print(
            f"[memory-worker] summary id={summary_id} session={session_id} "
            f"records={len(records)} period={period_start}..{period_end}",
            file=sys.stderr,
            flush=True,
        )
        return len(records)

    def _resolve_session_id(self) -> str | None:
        if self._config.session_id:
            return self._config.session_id
        checkpoint = self._store.get_checkpoint(ACTIVE_SESSION_KEY)
        if checkpoint:
            return checkpoint
        return self._infer_latest_session()

    def _infer_latest_session(self) -> str | None:
        session_id = self._store.latest_chat_session_id()
        if session_id is None:
            return None
        self._store.set_checkpoint(ACTIVE_SESSION_KEY, session_id)
        return session_id


def build_chat_context_lines(records: list[TextRecord]) -> str:
    return "\n".join(f"{record.author}: {record.text}" for record in records)
