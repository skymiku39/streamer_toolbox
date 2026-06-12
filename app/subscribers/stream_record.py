from __future__ import annotations

import argparse
import os
import sys
import threading

from dotenv import load_dotenv

from app.processes.registry import register_subscriber
from app.subscribers.stream_record_config import RecordConfig, routing_keys_for_mode
from app.subscribers.stream_record_writer import StreamRecordWriter
from pkg_bus.config import rabbitmq_url, stream_exchange
from pkg_bus.rabbitmq import connect_blocking, consume_messages, setup_subscriber_queue_bindings
from pkg_bus.topology import DEFAULT_EXCHANGE, QUEUE_STREAM_RECORD
from pkg_stream_store import StreamTextStore

PROCESS_NAME = "sub-stream-record"
STATS_INTERVAL_SECONDS = 30


@register_subscriber(
    name="sub-stream-record",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_STREAM_RECORD,
    description="chat.message / stt.segment → SQLite 記錄層",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(
        description="Subscribe chat.message / stt.segment → SQLite stream text store",
    )
    parser.add_argument(
        "--db-path",
        default=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),
    )
    parser.add_argument(
        "--session-id",
        default=os.environ.get("STREAM_SESSION_ID", ""),
        help="Optional fixed session id; default: {channel}_{YYYYMMDD}",
    )
    parser.add_argument(
        "--record-mode",
        default=os.environ.get("RECORD_MODE", "chat"),
        choices=["chat", "stt", "both"],
    )
    args = parser.parse_args(argv)

    config = RecordConfig.from_env()
    config = RecordConfig(
        db_path=args.db_path or config.db_path,
        session_id=(args.session_id or config.session_id or "").strip() or None,
        record_mode=(args.record_mode or config.record_mode).strip().lower(),
    )
    try:
        config.validate()
        routing_keys = routing_keys_for_mode(config.record_mode)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    store = StreamTextStore(config.db_path)
    writer = StreamRecordWriter(store, config)
    stop_stats = threading.Event()
    stats_thread = threading.Thread(
        target=lambda: _stats_loop(writer, stop_stats),
        daemon=True,
    )
    stats_thread.start()

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    setup_subscriber_queue_bindings(
        channel,
        exchange_name=stream_exchange(),
        queue_name=QUEUE_STREAM_RECORD,
        routing_keys=routing_keys,
    )

    print(
        f"{PROCESS_NAME} mode={config.record_mode} listening on {routing_keys} → {config.db_path}",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_STREAM_RECORD, writer.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        stop_stats.set()
        store.close()
        if connection.is_open:
            connection.close()
    return 0


def _stats_loop(writer: StreamRecordWriter, stop: threading.Event) -> None:
    while not stop.wait(STATS_INTERVAL_SECONDS):
        writer.log_stats()


if __name__ == "__main__":
    raise SystemExit(main())
