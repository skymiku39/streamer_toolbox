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
from ingress_discord.gateway import listen_with_reconnect
from ingress_discord.mapping import DiscordChatMessage, build_chat_event

PROCESS_NAME = "ingress-discord"


async def run(token: str, channel_id: int) -> None:
    connection = await connect_async(rabbitmq_url())
    mq_channel = await connection.channel()
    exchange = await declare_topic_exchange(mq_channel, stream_exchange())

    async def on_message(discord_msg: DiscordChatMessage) -> None:
        event = build_chat_event(discord_msg)
        await publish_topic(exchange, TOPIC_CHAT_MESSAGE, event.to_dict())
        print(
            f"published {event.message_id[:8]} #{event.channel} {event.author_name}",
            flush=True,
        )

    print(
        f"Listening to Discord channel {channel_id} via Gateway",
        file=sys.stderr,
        flush=True,
    )
    await listen_with_reconnect(token, channel_id, on_message)


@register_publisher(
    name="ingress-discord",
    exchange=DEFAULT_EXCHANGE,
    description="Discord Gateway → RabbitMQ chat.message",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Discord Gateway → RabbitMQ chat.message publisher"
    )
    parser.add_argument("--token", default=os.environ.get("DISCORD_BOT_TOKEN", ""))
    parser.add_argument("--channel-id", default=os.environ.get("DISCORD_CHANNEL_ID", ""))
    args = parser.parse_args(argv)

    token = (args.token or "").strip()
    if not token:
        print("DISCORD_BOT_TOKEN must be set or pass --token", file=sys.stderr)
        return 1

    channel_id_raw = (args.channel_id or "").strip()
    if not channel_id_raw:
        print("DISCORD_CHANNEL_ID must be set or pass --channel-id", file=sys.stderr)
        return 1

    try:
        channel_id = int(channel_id_raw)
    except ValueError:
        print("DISCORD_CHANNEL_ID must be a numeric snowflake ID", file=sys.stderr)
        return 1

    try:
        asyncio.run(run(token, channel_id))
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
