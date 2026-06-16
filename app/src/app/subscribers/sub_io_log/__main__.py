from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from events import TOPIC_CHAT_MESSAGE, ChatMessageEvent

from app.processes.registry import register_subscriber
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_blocking, consume_messages, setup_subscriber_queue
from bus.topology import DEFAULT_EXCHANGE, QUEUE_IO_LOG_CHAT_MESSAGE

PROCESS_NAME = "sub-io-log"
STATS_INTERVAL_SECONDS = 30


class IoLogSubscriber:
    def __init__(self, log_path: Path, console: bool) -> None:
        self._log_path = log_path
        self._console = console
        self._count = 0
        self._last_timestamp: str | None = None
        self._lock = threading.Lock()

    def handle(self, payload: dict) -> None:
        event = ChatMessageEvent.from_dict(payload)
        line = json.dumps(event.to_dict(), ensure_ascii=False)

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")

        with self._lock:
            self._count += 1
            self._last_timestamp = event.timestamp

        if self._console:
            now = datetime.now().strftime("%H:%M:%S")
            short_id = event.message_id[:8]
            print(
                f"[{now}] [{short_id}] #{event.channel} {event.author_name}: {event.content}",
                flush=True,
            )

    def stats_loop(self, stop: threading.Event) -> None:
        while not stop.wait(STATS_INTERVAL_SECONDS):
            with self._lock:
                count = self._count
                last_ts = self._last_timestamp
            print(
                f"[stats] received={count} last_timestamp={last_ts}",
                file=sys.stderr,
                flush=True,
            )


@register_subscriber(
    name="sub-io-log",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_IO_LOG_CHAT_MESSAGE,
    description="chat.message → console + JSONL",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Subscribe chat.message → console + JSONL")
    parser.add_argument(
        "--log-path",
        default=os.environ.get("IO_LOG_PATH", "logs/chat_io.jsonl"),
    )
    parser.add_argument(
        "--console",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("IO_LOG_CONSOLE", "true").lower() in {"1", "true", "yes"},
    )
    args = parser.parse_args(argv)

    log_path = Path(args.log_path)
    subscriber = IoLogSubscriber(log_path=log_path, console=args.console)
    stop_stats = threading.Event()
    stats_thread = threading.Thread(
        target=subscriber.stats_loop,
        args=(stop_stats,),
        daemon=True,
    )
    stats_thread.start()

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    setup_subscriber_queue(
        channel,
        exchange_name=stream_exchange(),
        queue_name=QUEUE_IO_LOG_CHAT_MESSAGE,
        routing_key=TOPIC_CHAT_MESSAGE,
    )

    print(f"Writing JSONL to {log_path}", file=sys.stderr, flush=True)
    try:
        consume_messages(channel, QUEUE_IO_LOG_CHAT_MESSAGE, subscriber.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        stop_stats.set()
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
