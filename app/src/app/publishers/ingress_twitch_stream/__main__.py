from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

from app.processes.registry import register_publisher
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_async, declare_topic_exchange, publish_topic
from bus.topology import DEFAULT_EXCHANGE
from events import TOPIC_STREAM_METADATA
from ingress_twitch_stream.fetcher import TwitchStreamFetcher
from ingress_twitch_stream.mapper import build_stream_metadata_event
from stream_store.idempotency import IdempotencyStore, default_idempotency_db_path

PROCESS_NAME = "ingress-twitch-stream"
NAMESPACE_STREAM_METADATA = "ingress.stream.metadata"
DEFAULT_POLL_SECONDS = 60
MIN_POLL_SECONDS = 10


async def run(channel: str, *, poll_seconds: int) -> None:
    connection = await connect_async(rabbitmq_url())
    mq_channel = await connection.channel()
    exchange = await declare_topic_exchange(mq_channel, stream_exchange())
    fetcher = TwitchStreamFetcher()
    idempotency = IdempotencyStore(default_idempotency_db_path())

    async def publish_snapshot() -> None:
        snapshot = await asyncio.to_thread(fetcher.fetch, channel)
        if snapshot is None:
            print(f"[{PROCESS_NAME}] fetch failed for #{channel}", file=sys.stderr, flush=True)
            return
        event = build_stream_metadata_event(snapshot)
        if not idempotency.claim(NAMESPACE_STREAM_METADATA, event.snapshot_id):
            return
        await publish_topic(exchange, TOPIC_STREAM_METADATA, event.to_dict())
        status = "LIVE" if event.is_live else "OFFLINE"
        duration = event.duration_seconds
        duration_text = f" {duration // 3600}h{(duration % 3600) // 60}m" if duration else ""
        game = event.game_name or "-"
        title = event.title or "-"
        print(
            f"published stream.metadata {status} #{event.channel} "
            f"game={game} title={title[:60]}{duration_text}",
            flush=True,
        )

    print(
        f"{PROCESS_NAME} polling #{channel.lstrip('#')} every {poll_seconds}s → stream.metadata",
        file=sys.stderr,
        flush=True,
    )
    try:
        while True:
            started = asyncio.get_running_loop().time()
            await publish_snapshot()
            elapsed = asyncio.get_running_loop().time() - started
            await asyncio.sleep(max(1.0, poll_seconds - elapsed))
    finally:
        idempotency.close()
        await connection.close()


@register_publisher(
    name="ingress-twitch-stream",
    exchange=DEFAULT_EXCHANGE,
    description="Twitch GQL 直播 metadata → stream.metadata",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Poll Twitch stream metadata (GQL) → RabbitMQ stream.metadata",
    )
    parser.add_argument(
        "--channel",
        default=os.environ.get("TWITCH_CHANNEL", ""),
        help="Twitch channel login (default: TWITCH_CHANNEL env)",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=int(os.environ.get("TWITCH_STREAM_POLL_SECONDS", str(DEFAULT_POLL_SECONDS))),
        help=f"Polling interval in seconds (min {MIN_POLL_SECONDS}, default {DEFAULT_POLL_SECONDS})",
    )
    args = parser.parse_args(argv)

    channel = (args.channel or "").strip().lstrip("#")
    if not channel:
        print("TWITCH_CHANNEL must be set or pass --channel", file=sys.stderr)
        return 1

    poll_seconds = max(MIN_POLL_SECONDS, args.poll_seconds)
    try:
        asyncio.run(run(channel, poll_seconds=poll_seconds))
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
