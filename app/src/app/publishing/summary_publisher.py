from __future__ import annotations

import os
import sys
from typing import Protocol

from events import TOPIC_MEMORY_SUMMARY_READY, MemorySummaryReadyEvent

from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_blocking, publish_topic_blocking
from stream_store.models import Summary


class SummaryPublisher(Protocol):
    def publish(self, summary: Summary) -> None:
        """摘要寫入 DB 後發布就緒事件。"""


class NoOpSummaryPublisher:
    def publish(self, summary: Summary) -> None:
        return


class RabbitMqSummaryPublisher:
    def publish(self, summary: Summary) -> None:
        event = MemorySummaryReadyEvent.build(
            summary_id=summary.id,
            session_id=summary.session_id,
            source=summary.source,
            period_start=summary.period_start,
            period_end=summary.period_end,
            record_count=summary.record_count,
            content=summary.content,
            created_at=summary.created_at,
        )
        connection = connect_blocking(rabbitmq_url())
        try:
            channel = connection.channel()
            publish_topic_blocking(
                channel,
                exchange_name=stream_exchange(),
                routing_key=TOPIC_MEMORY_SUMMARY_READY,
                payload=event.to_dict(),
            )
        finally:
            if connection.is_open:
                connection.close()
        print(
            f"[summary-publisher] published {TOPIC_MEMORY_SUMMARY_READY} id={summary.id} "
            f"session={summary.session_id} source={summary.source}",
            file=sys.stderr,
            flush=True,
        )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def create_summary_publisher() -> SummaryPublisher:
    if not _env_bool("MEMORY_PUBLISH_READY", True):
        return NoOpSummaryPublisher()
    return RabbitMqSummaryPublisher()
