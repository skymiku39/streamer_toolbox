from __future__ import annotations

import asyncio
import queue
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from emotes import EmoteRegistry
from ingress_ttv_read.mapper import map_chat_message
from ttvchat_lens import ChatMessage, LiveChatReader, parse_twitch_channel

PublishPayload = Callable[[dict[str, Any]], Awaitable[None]]

_RECONNECT_DELAY_SEC = 5.0


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
    *,
    reconnect_delay: float = _RECONNECT_DELAY_SEC,
) -> None:
    while not stop_event.is_set():
        reader = LiveChatReader(channel)
        reader.on_message(lambda msg: _enqueue(out_queue, msg))
        try:
            reader.start()
        except KeyboardInterrupt:
            break
        finally:
            reader.close()

        if stop_event.is_set():
            break

        time.sleep(reconnect_delay)

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

    thread = threading.Thread(
        target=_reader_worker,
        args=(normalized, out_queue, stop_event),
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
        thread.join(timeout=5)
