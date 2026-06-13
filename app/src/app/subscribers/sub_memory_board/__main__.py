from __future__ import annotations

import argparse
import os
import sys
import threading

from dotenv import load_dotenv

from app.console_encoding import configure_utf8_stdio
from app.memory_view.http_server import MemoryBoardHttpServer, MemoryBoardState
from app.memory_view.service import MemoryViewService
from app.processes.registry import register_subscriber
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_blocking, consume_messages, setup_subscriber_queue_bindings
from bus.topology import DEFAULT_EXCHANGE, QUEUE_MEMORY_BOARD
from events import TOPIC_MEMORY_SUMMARY_READY, MemorySummaryReadyEvent
from stream_store import StreamTextStore

configure_utf8_stdio()

PROCESS_NAME = "sub-memory-board"


class MemoryBoardRevisionListener:
    def __init__(self, state: MemoryBoardState) -> None:
        self._state = state
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="memory-board-mq",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        try:
            connection = connect_blocking(rabbitmq_url())
        except Exception as exc:
            print(f"[{PROCESS_NAME}] MQ unavailable: {exc}", file=sys.stderr, flush=True)
            return

        channel = connection.channel()
        exchange_name = stream_exchange()
        setup_subscriber_queue_bindings(
            channel,
            exchange_name=exchange_name,
            queue_name=QUEUE_MEMORY_BOARD,
            routing_keys=[TOPIC_MEMORY_SUMMARY_READY],
        )

        def on_message(payload: dict) -> None:
            try:
                event = MemorySummaryReadyEvent.from_dict(payload)
            except (KeyError, TypeError, ValueError):
                return
            self._state.bump()
            print(
                f"[{PROCESS_NAME}] summary ready id={event.summary_id} "
                f"session={event.session_id} source={event.source}",
                file=sys.stderr,
                flush=True,
            )

        print(
            f"[{PROCESS_NAME}] listening for {TOPIC_MEMORY_SUMMARY_READY}",
            file=sys.stderr,
            flush=True,
        )
        try:
            consume_messages(channel, QUEUE_MEMORY_BOARD, on_message)
        except Exception as exc:
            print(f"[{PROCESS_NAME}] MQ listener stopped: {exc}", file=sys.stderr, flush=True)
        finally:
            if connection.is_open:
                connection.close()


@register_subscriber(
    name="sub-memory-board",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_MEMORY_BOARD,
    description="L2 memory board — browse summaries via local HTTP",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(description="Browse L2 summaries in a local web board")
    parser.add_argument(
        "--db-path",
        default=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MEMORY_BOARD_HOST", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MEMORY_BOARD_PORT", "8765")),
    )
    parser.add_argument(
        "--no-mq",
        action="store_true",
        help="Disable memory.summary.ready listener (HTTP polling only)",
    )
    args = parser.parse_args(argv)

    if not os.path.isfile(args.db_path):
        print(f"找不到資料庫：{args.db_path}", file=sys.stderr)
        return 1

    store = StreamTextStore(args.db_path)
    service = MemoryViewService(store)
    state = MemoryBoardState()
    server = MemoryBoardHttpServer(
        host=args.host,
        port=args.port,
        service=service,
        state=state,
    )
    server.start()
    print(f"{PROCESS_NAME} {server.base_url}", file=sys.stderr, flush=True)

    listener: MemoryBoardRevisionListener | None = None
    mq_enabled = not args.no_mq and os.environ.get("MEMORY_BOARD_MQ", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if mq_enabled:
        listener = MemoryBoardRevisionListener(state)
        listener.start()

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        server.stop()
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
