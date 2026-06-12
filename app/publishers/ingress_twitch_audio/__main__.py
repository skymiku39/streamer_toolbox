from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import sys

from dotenv import load_dotenv

from app.processes.registry import register_publisher
from pkg_bus.topology import DEFAULT_EXCHANGE

from ingress_twitch_audio.config import SttConfig
from ingress_twitch_audio.live_audio import LiveAudioCapture
from ingress_twitch_audio.segment import build_stt_segment_event
from ingress_twitch_audio.stt_worker import STTWorker
from pkg_bus.config import rabbitmq_url, stream_exchange
from pkg_bus.rabbitmq import connect_async, declare_topic_exchange, publish_topic
from pkg_events import TOPIC_STT_SEGMENT

PROCESS_NAME = "ingress-twitch-audio"


async def run(channel: str, config: SttConfig) -> None:
    connection = await connect_async(rabbitmq_url())
    mq_channel = await connection.channel()
    exchange = await declare_topic_exchange(mq_channel, stream_exchange())
    loop = asyncio.get_running_loop()
    chunk_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=32)
    normalized_channel = channel.strip().lower().lstrip("#")

    def on_chunk(pcm: bytes) -> None:
        loop.call_soon_threadsafe(_enqueue_chunk, chunk_queue, pcm)

    def on_capture_error(msg: str) -> None:
        print(f"[capture-error] {msg}", file=sys.stderr, flush=True)

    def on_status(msg: str) -> None:
        print(f"[stt] {msg}", file=sys.stderr, flush=True)

    def on_stt_error(msg: str) -> None:
        print(f"[stt-error] {msg}", file=sys.stderr, flush=True)

    capture = LiveAudioCapture(
        normalized_channel,
        chunk_seconds=config.chunk_seconds,
        on_chunk=on_chunk,
        on_error=on_capture_error,
    )
    worker = STTWorker(
        config,
        on_status=on_status,
        on_error=on_stt_error,
    )
    worker.preload_in_background()

    capture.start()
    print(
        f"Capturing audio from #{normalized_channel} → stt.segment",
        file=sys.stderr,
        flush=True,
    )

    try:
        while True:
            pcm = await chunk_queue.get()
            if pcm is None:
                break
            if not worker.wait_until_ready(timeout=0.0):
                await asyncio.sleep(0.2)
                await _requeue_chunk(chunk_queue, pcm)
                continue

            segment = await asyncio.to_thread(worker.transcribe_chunk, pcm)
            if segment is None:
                continue

            event = build_stt_segment_event(
                normalized_channel,
                segment,
                language=config.language,
            )
            await publish_topic(exchange, TOPIC_STT_SEGMENT, event.to_dict())
            short_id = event.segment_id[:8]
            preview = event.text if len(event.text) <= 60 else f"{event.text[:57]}..."
            print(
                f"published {short_id} [{event.start_sec:.1f}-{event.end_sec:.1f}s] {preview}",
                flush=True,
            )
    finally:
        capture.stop()
        await connection.close()


def _enqueue_chunk(queue: asyncio.Queue[bytes | None], pcm: bytes) -> None:
    try:
        queue.put_nowait(pcm)
    except asyncio.QueueFull:
        with contextlib.suppress(asyncio.QueueEmpty):
            queue.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(pcm)


async def _requeue_chunk(queue: asyncio.Queue[bytes | None], pcm: bytes) -> None:
    try:
        queue.put_nowait(pcm)
    except asyncio.QueueFull:
        pass


@register_publisher(
    name="ingress-twitch-audio",
    exchange=DEFAULT_EXCHANGE,
    description="Twitch live audio STT → RabbitMQ stt.segment",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Twitch live audio STT → RabbitMQ stt.segment publisher",
    )
    parser.add_argument("--channel", default=os.environ.get("TWITCH_CHANNEL", ""))
    args = parser.parse_args(argv)

    channel = (args.channel or "").strip()
    if not channel:
        print("TWITCH_CHANNEL must be set or pass --channel", file=sys.stderr)
        return 1

    config = SttConfig.from_env()
    try:
        asyncio.run(run(channel, config))
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
