from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from emotes import EmoteRegistry
from ingress_ttv_read.mapper import map_chat_message
from ttvchat_lens import ChatMessage, LiveChatReader, parse_twitch_channel

PublishPayload = Callable[[dict[str, Any]], Awaitable[None]]

_RECONNECT_DELAY_SEC = 5.0


class _CurrentReader:
    """thread-safe 持有目前運行中的 LiveChatReader，供關閉時主動中斷阻塞迴圈。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reader: LiveChatReader | None = None

    def set(self, reader: LiveChatReader | None) -> None:
        with self._lock:
            self._reader = reader

    def stop(self) -> None:
        with self._lock:
            reader = self._reader
        if reader is not None:
            reader.stop()


def _enqueue(out_queue: queue.Queue[ChatMessage | None], message: ChatMessage) -> None:
    try:
        out_queue.put_nowait(message)
    except queue.Full:
        try:
            out_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            out_queue.put_nowait(message)
        except queue.Full:
            pass


def _reader_worker(
    channel: str,
    out_queue: queue.Queue[ChatMessage | None],
    stop_event: threading.Event,
    current: _CurrentReader,
    *,
    reconnect_delay: float = _RECONNECT_DELAY_SEC,
) -> None:
    while not stop_event.is_set():
        reader = LiveChatReader(channel)
        reader.on_message(lambda msg: _enqueue(out_queue, msg))
        current.set(reader)
        try:
            reader.start()
        except KeyboardInterrupt:
            break
        finally:
            current.set(None)
            reader.close()

        # 以 stop_event.wait 取代固定 sleep：關閉時可立即喚醒，不必卡滿 reconnect_delay
        if stop_event.wait(reconnect_delay):
            break

    out_queue.put(None)


async def run_publisher(
    channel: str,
    publish: PublishPayload,
    *,
    queue_size: int = 2048,
    reconnect_delay: float = _RECONNECT_DELAY_SEC,
    emote_registry: EmoteRegistry | None = None,
) -> None:
    """包裝 LiveChatReader：handler 僅入隊，async 迴圈負責 publish。"""
    normalized = parse_twitch_channel(channel)
    out_queue: queue.Queue[ChatMessage | None] = queue.Queue(maxsize=queue_size)
    stop_event = threading.Event()
    current_reader = _CurrentReader()

    thread = threading.Thread(
        target=_reader_worker,
        args=(normalized, out_queue, stop_event, current_reader),
        kwargs={"reconnect_delay": reconnect_delay},
        daemon=True,
        name="ingress-ttv-read",
    )
    thread.start()

    loop = asyncio.get_running_loop()
    try:
        while True:
            msg = await loop.run_in_executor(None, out_queue.get)
            if msg is None:
                if stop_event.is_set():
                    break
                continue

            event = map_chat_message(msg, normalized, emote_registry=emote_registry)
            if event is None:
                continue

            await publish(event.to_dict())
    finally:
        stop_event.set()
        current_reader.stop()
        thread.join(timeout=5)
