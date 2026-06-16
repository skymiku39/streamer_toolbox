from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from events import TOPIC_CHAT_REPLY

from app.processes.registry import register_subscriber
from app.subscribers.qa_memory_mode import resolve_qa_memory_mode
from app.subscribers.stream_record_config import RecordConfig
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_blocking, consume_messages, setup_subscriber_queue_bindings
from bus.topology import DEFAULT_EXCHANGE, QUEUE_QA_MEMORY_BATCH
from stream_store import StreamTextStore
from stream_store.idempotency import IdempotencyStore, default_idempotency_db_path
from sub_qa_memory_batch.writer import BatchQaMemoryWriter

PROCESS_NAME = "sub-qa-memory-batch"
NAMESPACE = "sub_qa_memory_batch.reply"


@register_subscriber(
    name="sub-qa-memory-batch",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_QA_MEMORY_BATCH,
    description="chat.reply(logic-llm) → text_records，交由 L2 批次摘要",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Subscribe chat.reply → queue bot Q&A for L2 batch summarization",
    )
    parser.add_argument(
        "--db-path",
        default=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),
    )
    args = parser.parse_args(argv)

    if resolve_qa_memory_mode() != "batch":
        print(
            f"[{PROCESS_NAME}] disabled (QA_MEMORY_MODE={resolve_qa_memory_mode()!r}, "
            "need 'batch')",
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
    writer = BatchQaMemoryWriter(store, config)
    idempotency = IdempotencyStore(default_idempotency_db_path())

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    exchange_name = stream_exchange()
    setup_subscriber_queue_bindings(
        channel,
        exchange_name=exchange_name,
        queue_name=QUEUE_QA_MEMORY_BATCH,
        routing_keys=[TOPIC_CHAT_REPLY],
    )

    def handle(payload: dict) -> None:
        correlation_id = str(payload.get("correlation_id", "")).strip()
        if correlation_id and not idempotency.claim(NAMESPACE, correlation_id):
            print(
                f"[{PROCESS_NAME}] skip duplicate correlation={correlation_id[:8]}",
                file=sys.stderr,
                flush=True,
            )
            return
        try:
            if not writer.handle(payload):
                if correlation_id:
                    idempotency.release(NAMESPACE, correlation_id)
        except Exception:
            if correlation_id:
                idempotency.release(NAMESPACE, correlation_id)
            raise

    print(
        f"{PROCESS_NAME} listening on {TOPIC_CHAT_REPLY} (logic-llm only)",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_QA_MEMORY_BATCH, handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        idempotency.close()
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
