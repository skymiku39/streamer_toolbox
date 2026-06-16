from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from events import TOPIC_CHAT_MESSAGE

from app.processes.registry import register_publisher
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_async, declare_topic_exchange, publish_topic
from bus.topology import DEFAULT_EXCHANGE
from emotes import EmoteRegistry
from ingress_ttv_read.publisher import run_publisher
from stream_store.idempotency import IdempotencyStore, default_idempotency_db_path

PROCESS_NAME = "ingress-ttv-read"
NAMESPACE_CHAT_MESSAGE = "ingress.chat.message"


async def run(channel: str) -> None:
    connection = await connect_async(rabbitmq_url())
    mq_channel = await connection.channel()
    exchange = await declare_topic_exchange(mq_channel, stream_exchange())
    dedup_db_path = default_idempotency_db_path()
    idempotency = IdempotencyStore(dedup_db_path)

    async def publish(payload: dict) -> None:
        message_id = str(payload.get("message_id", "")).strip()
        content = str(payload.get("content", "")).strip()
        if message_id and not idempotency.claim(NAMESPACE_CHAT_MESSAGE, message_id):
            print(
                f"skip duplicate chat.message message_id={message_id[:8]}",
                file=sys.stderr,
                flush=True,
            )
            return
        await publish_topic(exchange, TOPIC_CHAT_MESSAGE, payload)
        message_id_short = payload.get("message_id", "")[:8]
        author = payload.get("author_name", "")
        ch = payload.get("channel", "")
        preview = content if len(content) <= 60 else f"{content[:57]}..."
        print(f"published {message_id_short} #{ch} {author}: {preview}", flush=True)

    print(
        f"Listening to #{channel.lstrip('#')} via ttvchat_lens (anonymous IRC)",
        file=sys.stderr,
        flush=True,
    )

    emote_registry = await EmoteRegistry.load_for_channel_login(channel.lstrip("#"))
    if emote_registry.token_map:
        print(
            f"Loaded {len(emote_registry.token_map)} third-party emote tokens",
            file=sys.stderr,
            flush=True,
        )

    try:
        await run_publisher(channel, publish, emote_registry=emote_registry)
    finally:
        idempotency.close()
        await connection.close()


@register_publisher(
    name="ingress-ttv-read",
    exchange=DEFAULT_EXCHANGE,
    description="ttvchat_lens IRC → RabbitMQ chat.message",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Twitch IRC (ttvchat_lens) → RabbitMQ chat.message publisher"
    )
    parser.add_argument(
        "--channel",
        default=os.environ.get("TWITCH_CHANNEL", ""),
        help="Twitch channel name or URL (default: TWITCH_CHANNEL env)",
    )
    args = parser.parse_args(argv)

    channel = (args.channel or "").strip()
    if not channel:
        print("TWITCH_CHANNEL must be set or pass --channel", file=sys.stderr)
        return 1

    try:
        asyncio.run(run(channel))
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

