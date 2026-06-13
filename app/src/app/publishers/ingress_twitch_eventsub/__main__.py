from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from app.processes.registry import register_publisher
from bus.topology import DEFAULT_EXCHANGE

from identity_oauth import EnvTokenProvider
from ingress_twitch_eventsub.bot import EventSubIngressBot
from ingress_twitch_eventsub.publisher import MqEventPublisher
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_async, declare_topic_exchange

PROCESS_NAME = "ingress-twitch-eventsub"
logger = logging.getLogger(PROCESS_NAME)


async def run(channel: str) -> None:
    token_provider = EnvTokenProvider()
    creds = await token_provider.get_credentials()

    missing = [
        name
        for name, value in {
            "TWITCH_CLIENT_ID": creds.client_id,
            "TWITCH_CLIENT_SECRET": creds.client_secret,
            "TWITCH_BOT_ID": creds.bot_id,
            "TWITCH_BROADCASTER_ID": creds.broadcaster_id,
            "TWITCH_ACCESS_TOKEN": creds.access_token,
            "TWITCH_REFRESH_TOKEN": creds.refresh_token,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required OAuth env: {', '.join(missing)}")

    connection = await connect_async(rabbitmq_url())
    mq_channel = await connection.channel()
    exchange = await declare_topic_exchange(mq_channel, stream_exchange())
    publisher = MqEventPublisher(exchange)

    normalized_channel = channel.lstrip("#")
    bot = EventSubIngressBot(
        client_id=creds.client_id,
        client_secret=creds.client_secret,
        bot_id=creds.bot_id,
        token=creds.access_token,
        refresh_token=creds.refresh_token,
        channels=[normalized_channel],
        broadcaster_id=creds.broadcaster_id,
        broadcaster_type=creds.broadcaster_type,
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
