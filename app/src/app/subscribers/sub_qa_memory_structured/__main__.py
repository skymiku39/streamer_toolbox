from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from app.processes.registry import register_subscriber
from app.subscribers.stream_record_config import RecordConfig
from app.publishing.summary_publisher import create_summary_publisher
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_blocking, consume_messages, setup_subscriber_queue_bindings
from bus.topology import DEFAULT_EXCHANGE, QUEUE_QA_MEMORY_STRUCTURED
from events import TOPIC_MEMORY_QA_RECORD
from stream_store import StreamTextStore
from stream_store.idempotency import IdempotencyStore, default_idempotency_db_path

from sub_qa_memory_structured.writer import StructuredQaMemoryWriter
from app.subscribers.qa_memory_mode import resolve_qa_memory_mode

PROCESS_NAME = "sub-qa-memory-structured"
NAMESPACE = "sub_qa_memory_structured.record"


@register_subscriber(
    name="sub-qa-memory-structured",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_QA_MEMORY_STRUCTURED,
    description="memory.qa.record → SQLite summaries(source=qa) + memory.summary.ready",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Subscribe memory.qa.record → persist QA memory for RAG",
    )
    parser.add_argument(
        "--db-path",
        default=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),
    )
    args = parser.parse_args(argv)

    if resolve_qa_memory_mode() != "structured":
        print(
            f"[{PROCESS_NAME}] disabled (QA_MEMORY_MODE={resolve_qa_memory_mode()!r}, "
            "need 'structured')",
            file=sys.stderr,
        )
        return 0

    config = RecordConfig.from_env()
    config = RecordConfig(
        db_path=args.db_path or config.db_path,
        session_id=config.session_id,
        record_mode=config.record_mode,
    )
    store = StreamTextStore(config.db_path)
    writer = StructuredQaMemoryWriter(store, config)
    publisher = create_summary_publisher()
    idempotency = IdempotencyStore(default_idempotency_db_path())

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    exchange_name = stream_exchange()
    setup_subscriber_queue_bindings(
        channel,
        exchange_name=exchange_name,
        queue_name=QUEUE_QA_MEMORY_STRUCTURED,
        routing_keys=[TOPIC_MEMORY_QA_RECORD],
    )

    def handle(payload: dict) -> None:
        event = payload if isinstance(payload, dict) else {}
        correlation_id = str(event.get("correlation_id", "")).strip()
        if correlation_id and not idempotency.claim(NAMESPACE, correlation_id):
            print(
                f"[{PROCESS_NAME}] skip duplicate correlation={correlation_id[:8]}",
                file=sys.stderr,
                flush=True,
            )
            return
        try:
            summary = writer.handle(payload)
            if summary is not None:
                publisher.publish(summary)
        except Exception:
            if correlation_id:
                idempotency.release(NAMESPACE, correlation_id)
            raise

    print(
        f"{PROCESS_NAME} listening on {TOPIC_MEMORY_QA_RECORD}",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_QA_MEMORY_STRUCTURED, handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        idempotency.close()
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
