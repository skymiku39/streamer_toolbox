from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, field

from events import TOPIC_MEMORY_SUMMARIZE_REQUEST, MemorySummarizeRequestEvent

from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import (
    connect_blocking,
    consume_messages,
    publish_topic_blocking,
    setup_subscriber_queue_bindings,
)
from bus.topology import QUEUE_MEMORY_WORKER


@dataclass
class MemoryTriggerHandle:
    """常駐 worker 與觸發發布端共用的同步狀態。"""

    _event: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _pending_session_id: str | None = None

    def signal(self, *, session_id: str | None = None) -> None:
        with self._lock:
            if session_id:
                self._pending_session_id = session_id
            self._event.set()

    def wait(self, timeout: float) -> bool:
        triggered = self._event.wait(timeout=timeout)
        if triggered:
            self._event.clear()
        return triggered

    def consume_session_id(self) -> str | None:
        with self._lock:
            session_id = self._pending_session_id
            self._pending_session_id = None
        return session_id


class MemoryTriggerListener:
    def __init__(self, handle: MemoryTriggerHandle) -> None:
        self._handle = handle
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="memory-trigger-listener",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        try:
            connection = connect_blocking(rabbitmq_url())
        except Exception as exc:
            print(
                f"[memory-worker] trigger listener failed to connect: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return

        channel = connection.channel()
        exchange_name = stream_exchange()
        setup_subscriber_queue_bindings(
            channel,
            exchange_name=exchange_name,
            queue_name=QUEUE_MEMORY_WORKER,
            routing_keys=[TOPIC_MEMORY_SUMMARIZE_REQUEST],
        )

        def on_message(payload: dict) -> None:
            try:
                event = MemorySummarizeRequestEvent.from_dict(payload)
            except (KeyError, TypeError, ValueError) as exc:
                print(
                    f"[memory-worker] ignored invalid trigger payload: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                return
            session_hint = event.session_id or "(auto)"
            print(
                f"[memory-worker] trigger received source={event.source!r} "
                f"reason={event.reason!r} session={session_hint}",
                file=sys.stderr,
                flush=True,
            )
            self._handle.signal(session_id=event.session_id)

        print(
            f"[memory-worker] listening for {TOPIC_MEMORY_SUMMARIZE_REQUEST}",
            file=sys.stderr,
            flush=True,
        )
        try:
            consume_messages(channel, QUEUE_MEMORY_WORKER, on_message)
        except Exception as exc:
            print(
                f"[memory-worker] trigger listener stopped: {exc}",
                file=sys.stderr,
                flush=True,
            )
        finally:
            if connection.is_open:
                connection.close()


def publish_memory_summarize_trigger(
    *,
    session_id: str | None = None,
    reason: str = "manual",
    source: str = "cli",
) -> None:
    event = MemorySummarizeRequestEvent.build(
        session_id=session_id,
        reason=reason,
        source=source,
    )
    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    exchange_name = stream_exchange()
    publish_topic_blocking(
        channel,
        exchange_name=exchange_name,
        routing_key=TOPIC_MEMORY_SUMMARIZE_REQUEST,
        payload=event.to_dict(),
    )
    connection.close()
    session_hint = session_id or "(auto)"
    print(
        f"[memory-worker] published {TOPIC_MEMORY_SUMMARIZE_REQUEST} session={session_hint}",
        file=sys.stderr,
        flush=True,
    )
