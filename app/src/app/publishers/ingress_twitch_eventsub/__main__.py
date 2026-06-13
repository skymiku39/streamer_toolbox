from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from app.processes.registry import register_publisher
from bus.topology import DEFAULT_EXCHANGE

from identity_oauth import MultiAccountTokenProvider
from ingress_twitch_eventsub.bot import EventSubIngressBot
from ingress_twitch_eventsub.publisher import MqEventPublisher
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_async, declare_topic_exchange, publish_topic
from events import TOPIC_CHAT_MESSAGE
from stream_store.idempotency import IdempotencyStore, default_idempotency_db_path

PROCESS_NAME = "ingress-twitch-eventsub"
NAMESPACE_CHAT_MESSAGE = "ingress.chat.message"
logger = logging.getLogger(PROCESS_NAME)


async def run(channel: str) -> None:
    token_provider = MultiAccountTokenProvider()
    channel_creds = await token_provider.get_credentials("channel")
    bot_creds = await token_provider.get_credentials("bot")

    missing: list[str] = []
    if not channel_creds.client_id:
        missing.append("TWITCH_CLIENT_ID")
    if not channel_creds.client_secret:
        missing.append("TWITCH_CLIENT_SECRET")
    if not channel_creds.broadcaster_id:
        missing.append("TWITCH_BROADCASTER_ID")
    if not bot_creds.bot_id:
        missing.append("TWITCH_BOT_ID")
    if not channel_creds.access_token:
        missing.append(
            "channel access token (TWITCH_CHANNEL_REFRESH_TOKEN or TWITCH_REFRESH_TOKEN)",
        )
    if not bot_creds.access_token:
        missing.append("bot access token (TWITCH_BOT_REFRESH_TOKEN or TWITCH_REFRESH_TOKEN)")
    if missing:
        raise RuntimeError(f"Missing required OAuth env: {', '.join(missing)}")

    connection = await connect_async(rabbitmq_url())
    mq_channel = await connection.channel()
    exchange = await declare_topic_exchange(mq_channel, stream_exchange())
    dedup_db_path = default_idempotency_db_path()
    idempotency = IdempotencyStore(dedup_db_path)

    async def publish_chat(payload: dict) -> None:
        message_id = str(payload.get("message_id", "")).strip()
        if message_id and not idempotency.claim(NAMESPACE_CHAT_MESSAGE, message_id):
            print(
                f"skip duplicate chat.message message_id={message_id[:8]}",
                file=sys.stderr,
                flush=True,
            )
            return
        await publish_topic(exchange, TOPIC_CHAT_MESSAGE, payload)

    publisher = MqEventPublisher(exchange, publish_chat=publish_chat)

    normalized_channel = channel.lstrip("#")
    bot = EventSubIngressBot(
        client_id=channel_creds.client_id,
        client_secret=channel_creds.client_secret,
        bot_id=bot_creds.bot_id,
        token=bot_creds.access_token,
        refresh_token=bot_creds.refresh_token,
        channel_token=channel_creds.access_token,
        channel_refresh_token=channel_creds.refresh_token,
        channels=[normalized_channel],
        broadcaster_id=channel_creds.broadcaster_id,
        broadcaster_type=channel_creds.broadcaster_type,
        publisher=publisher,
    )

    print(
        f"Starting EventSub ingress for #{normalized_channel} (chat_read via EventSub)",
        file=sys.stderr,
        flush=True,
    )
    try:
        await bot.start()
    finally:
        idempotency.close()
        if connection.is_closed is False:
            await connection.close()


@register_publisher(
    name="ingress-twitch-eventsub",
    exchange=DEFAULT_EXCHANGE,
    description="Twitch EventSub → RabbitMQ chat.message / eventsub.*",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Twitch EventSub → RabbitMQ chat.message / eventsub.* publisher",
    )
    parser.add_argument("--channel", default=os.environ.get("TWITCH_CHANNEL", ""))
    args = parser.parse_args(argv)

    channel = (args.channel or "").strip()
    if not channel:
        print("TWITCH_CHANNEL must be set or pass --channel", file=sys.stderr)
        return 1

    try:
        asyncio.run(run(channel))
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
