from __future__ import annotations

import sys
import threading
from typing import Any

from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_blocking, consume_messages, setup_subscriber_queue
from bus.topology import QUEUE_SHOW_OVERLAY_CHAT_MESSAGE
from events import TOPIC_CHAT_MESSAGE

from sub_show_overlay.http_server import OverlayHttpServer
from sub_show_overlay.queue import OverlayMessageQueue
from sub_show_overlay.settings import OverlaySettings
from sub_show_overlay.worker import OverlayRenderWorker

STATS_INTERVAL_SECONDS = 30


class ShowOverlaySubscriber:
    def __init__(self, settings: OverlaySettings) -> None:
        self._settings = settings
        self._message_queue = OverlayMessageQueue(maxsize=settings.queue_size)
        self._worker = OverlayRenderWorker(settings, self._message_queue)
        self._http = OverlayHttpServer(
            host=settings.http_host,
            port=settings.http_port,
            snapshot_provider=self._snapshot_payload,
        )
        self._stop_stats = threading.Event()

    def handle(self, payload: dict[str, Any]) -> None:
        self._message_queue.put(payload)

    def _snapshot_payload(self) -> dict:
        writers = self._worker.writers
        if not writers:
            return {}
        return writers[0].snapshot_dict()

    def stats_loop(self) -> None:
        while not self._stop_stats.wait(STATS_INTERVAL_SECONDS):
            queue_stats = self._message_queue.stats()
            print(
                "[stats] "
                f"received={queue_stats.received} "
                f"enqueued={queue_stats.enqueued} "
                f"dropped={queue_stats.dropped} "
                f"coalesced={queue_stats.coalesced} "
                f"rendered={self._worker.processed_count}",
                file=sys.stderr,
                flush=True,
            )

    def run(self) -> None:
        self._worker.start()
        self._http.start()
        print(
            f"Overlay HTTP: {self._http.base_url} (OBS Browser Source)",
            file=sys.stderr,
            flush=True,
        )
        for ipc_path in self._settings.ipc_paths:
            print(f"Overlay IPC: {ipc_path}", file=sys.stderr, flush=True)

        stats_thread = threading.Thread(target=self.stats_loop, name="overlay-stats", daemon=True)
        stats_thread.start()

        connection = connect_blocking(rabbitmq_url())
        channel = connection.channel()
        setup_subscriber_queue(
            channel,
            exchange_name=stream_exchange(),
            queue_name=QUEUE_SHOW_OVERLAY_CHAT_MESSAGE,
            routing_key=TOPIC_CHAT_MESSAGE,
        )

        try:
            consume_messages(channel, QUEUE_SHOW_OVERLAY_CHAT_MESSAGE, self.handle)
        except KeyboardInterrupt:
            print("Shutting down...", file=sys.stderr)
        finally:
            self._stop_stats.set()
            if connection.is_open:
                connection.close()
            self._worker.stop()
            self._http.stop()
