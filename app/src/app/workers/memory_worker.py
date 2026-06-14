from __future__ import annotations

import sys
from collections.abc import Callable
from functools import partial

from stream_store import StreamTextStore, resolve_session_for_channel
from stream_store.models import Summary, TextRecord

from app.workers.memory_config import MemoryWorkerConfig
from app.publishing.summary_publisher import NoOpSummaryPublisher, SummaryPublisher
from app.workers.memory_summarizer import Summarizer


class MemoryWorker:
    def __init__(
        self,
        store: StreamTextStore,
        config: MemoryWorkerConfig,
        summarizer: Summarizer,
        *,
        summary_publisher: SummaryPublisher | None = None,
    ) -> None:
        self._store = store
        self._config = config
        self._summarizer = summarizer
        self._summary_publisher = summary_publisher or NoOpSummaryPublisher()

    def run_once(self, *, session_id: str | None = None) -> int:
        resolved_session_id = session_id or self._resolve_session_id()
        if resolved_session_id is None:
            print("[memory-worker] no session yet; waiting for records", file=sys.stderr)
            return 0

        if self._config.record_mode == "both":
            return self._summarize_both_aligned(resolved_session_id)

        processed = 0
        if self._config.include_chat:
            processed += self._summarize_source(
                resolved_session_id,
                source="chat",
                fetch=partial(self._store.fetch_unsummarized_chat, channel=self._config.channel),
                summarize=self._summarizer.summarize_chat,
            )
        if self._config.include_stt:
            processed += self._summarize_source(
                resolved_session_id,
                source="stt",
                fetch=partial(self._store.fetch_unsummarized_stt, channel=self._config.channel),
                summarize=self._summarizer.summarize_stt,
            )
        return processed

    def _summarize_both_aligned(self, session_id: str) -> int:
        """依合併時間軸取一批紀錄，chat / stt 分開摘要但共用同一 period。"""
        batch = self._store.fetch_unsummarized_merged(
            session_id,
            sources=["chat", "stt"],
            channel=self._config.channel,
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
        summary = self._store.save_summary(
            session_id=session_id,
            period_start=period_start,
            period_end=period_end,
            source=source,
            content=content,
            record_count=len(records),
        )
        self._summary_publisher.publish(summary)
        channel_hint = self._config.channel or records[0].channel
        print(
            f"[memory-worker] summary id={summary.id} session={session_id} channel={channel_hint} "
            f"source={source} records={len(records)} period={period_start}..{period_end}",
            file=sys.stderr,
            flush=True,
        )
        return len(records)

    def _resolve_session_id(self) -> str | None:
        if self._config.session_id and self._config.channel:
            from stream_store.session import normalize_channel

            normalized = normalize_channel(self._config.channel)
            if self._config.session_id.startswith(f"{normalized}_"):
                return self._config.session_id
        elif self._config.session_id:
            return self._config.session_id
        channel = self._config.channel
        if channel:
            return resolve_session_for_channel(
                self._store,
                channel,
                explicit_session_id=self._config.session_id,
            )
        return resolve_session_for_channel(self._store, "")


def build_chat_context_lines(records: list[TextRecord]) -> str:
    return "\n".join(f"{record.author}: {record.text}" for record in records)
