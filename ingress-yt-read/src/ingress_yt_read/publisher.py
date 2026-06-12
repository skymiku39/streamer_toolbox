from __future__ import annotations

import asyncio
import queue
import sys
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from tubechat_lens.reader import ChatMessage, LiveChatReader, normalize_video_id

from ingress_yt_read.mapper import map_chat_message

PublishPayload = Callable[[dict[str, Any]], Awaitable[None]]


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
    video: str,
    out_queue: queue.Queue[ChatMessage | None],
    stop_event: threading.Event,
) -> None:
    reader = LiveChatReader(video)
    reader.on_message(lambda msg: _enqueue(out_queue, msg))
    try:
        reader.start()
    except KeyboardInterrupt:
        pass
    finally:
        reader.close()
        print("YouTube live chat ended or reader stopped", file=sys.stderr, flush=True)

    out_queue.put(None)


async def run_publisher(
    video: str,
    publish: PublishPayload,
    *,
    queue_size: int = 2048,
) -> None:
    """包裝 LiveChatReader：handler 僅入隊，async 迴圈負責 publish。"""

    channel = normalize_video_id(video)
    out_queue: queue.Queue[ChatMessage | None] = queue.Queue(maxsize=queue_size)
    stop_event = threading.Event()

    thread = threading.Thread(
        target=_reader_worker,
        args=(video, out_queue, stop_event),
        daemon=True,
        name="ingress-yt-read",
    )
    thread.start()

    loop = asyncio.get_running_loop()
    try:
        while True:
            msg = await loop.run_in_executor(None, out_queue.get)
            if msg is None:
                break

            event = map_chat_message(msg, channel)
            await publish(event.to_dict())
    finally:
        stop_event.set()
        thread.join(timeout=5)
