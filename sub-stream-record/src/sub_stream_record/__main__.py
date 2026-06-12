from __future__ import annotations

import argparse
import os
import sys
import threading

from dotenv import load_dotenv

from pkg_bus.config import rabbitmq_url, stream_exchange
from pkg_bus.rabbitmq import connect_blocking, consume_messages, setup_subscriber_queue
from pkg_bus.topology import QUEUE_STREAM_RECORD_CHAT_MESSAGE
from pkg_events import TOPIC_CHAT_MESSAGE
from pkg_stream_store import StreamTextStore

from sub_stream_record.config import RecordConfig
from sub_stream_record.writer import ChatRecordWriter

PROCESS_NAME = "sub-stream-record"
STATS_INTERVAL_SECONDS = 30


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(
        description="Subscribe chat.message → SQLite stream text store (Phase 1: chat only)",
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
    args = parser.parse_args(argv)

    config = RecordConfig.from_env()
    if args.db_path:
        config = RecordConfig(
            db_path=args.db_path,
            session_id=(args.session_id or config.session_id or "").strip() or None,
            record_mode=config.record_mode,
        )
    try:
        config.validate()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    store = StreamTextStore(config.db_path)
    writer = ChatRecordWriter(store, config)
    stop_stats = threading.Event()
    stats_thread = threading.Thread(
        target=lambda: _stats_loop(writer, stop_stats),
        daemon=True,
    )
    stats_thread.start()

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    setup_subscriber_queue(
        channel,
        exchange_name=stream_exchange(),
        queue_name=QUEUE_STREAM_RECORD_CHAT_MESSAGE,
        routing_key=TOPIC_CHAT_MESSAGE,
    )

    print(
        f"{PROCESS_NAME} listening on {TOPIC_CHAT_MESSAGE} → {config.db_path}",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_STREAM_RECORD_CHAT_MESSAGE, writer.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        stop_stats.set()
        store.close()
        if connection.is_open:
            connection.close()
    return 0


def _stats_loop(writer: ChatRecordWriter, stop: threading.Event) -> None:
    while not stop.wait(STATS_INTERVAL_SECONDS):
        writer.log_stats()


if __name__ == "__main__":
    raise SystemExit(main())
