from __future__ import annotations

import sys
from collections.abc import Callable

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
            print("[memory-worker] no session yet; waiting for records", file=sys.stderr)
            return 0

        if self._config.record_mode == "both":
            return self._summarize_both_aligned(session_id)

        processed = 0
        if self._config.include_chat:
            processed += self._summarize_source(
                session_id,
                source="chat",
                fetch=self._store.fetch_unsummarized_chat,
                summarize=self._summarizer.summarize_chat,
            )
        if self._config.include_stt:
            processed += self._summarize_source(
                session_id,
                source="stt",
                fetch=self._store.fetch_unsummarized_stt,
                summarize=self._summarizer.summarize_stt,
            )
        return processed

    def _summarize_both_aligned(self, session_id: str) -> int:
        """依合併時間軸取一批紀錄，chat / stt 分開摘要但共用同一 period。"""
        batch = self._store.fetch_unsummarized_merged(
            session_id,
            sources=["chat", "stt"],
            limit=self._config.batch_limit,
        )
        if not batch:
            return 0

        period_start = batch[0].timestamp
        period_end = batch[-1].timestamp
        chat_records = [record for record in batch if record.source == "chat"]
        stt_records = [record for record in batch if record.source == "stt"]

        processed = 0
        if chat_records:
            processed += self._save_summary(
                session_id,
                source="chat",
                records=chat_records,
                period_start=period_start,
                period_end=period_end,
                summarize=self._summarizer.summarize_chat,
            )
        if stt_records:
            processed += self._save_summary(
                session_id,
                source="stt",
                records=stt_records,
                period_start=period_start,
                period_end=period_end,
                summarize=self._summarizer.summarize_stt,
            )

        self._store.mark_summarized([record.id for record in batch])
        return processed

    def _summarize_source(
        self,
        session_id: str,
        *,
        source: str,
        fetch: Callable[..., list[TextRecord]],
        summarize: Callable[[list[TextRecord]], str],
    ) -> int:
        records = fetch(session_id, limit=self._config.batch_limit)
        if not records:
            return 0

        period_start = records[0].timestamp
        period_end = records[-1].timestamp
        count = self._save_summary(
            session_id,
            source=source,
            records=records,
            period_start=period_start,
            period_end=period_end,
            summarize=summarize,
        )
        self._store.mark_summarized([record.id for record in records])
        return count

    def _save_summary(
        self,
        session_id: str,
        *,
        source: str,
        records: list[TextRecord],
        period_start: str,
        period_end: str,
        summarize: Callable[[list[TextRecord]], str],
    ) -> int:
        content = summarize(records)
        summary_id = self._store.save_summary(
            session_id=session_id,
            period_start=period_start,
            period_end=period_end,
            source=source,
            content=content,
            record_count=len(records),
        )
        print(
            f"[memory-worker] summary id={summary_id} session={session_id} source={source} "
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
        session_id = self._store.latest_session_id()
        if session_id is None:
            return None
        self._store.set_checkpoint(ACTIVE_SESSION_KEY, session_id)
        return session_id


def build_chat_context_lines(records: list[TextRecord]) -> str:
    return "\n".join(f"{record.author}: {record.text}" for record in records)
