from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime

from dotenv import load_dotenv

from ingress_twitch_chat.twitch_irc import IrcChatMessage, listen_anonymous_with_reconnect
from pkg_bus.config import rabbitmq_url, stream_exchange
from pkg_bus.rabbitmq import connect_async, declare_topic_exchange, publish_topic
from pkg_events import TOPIC_CHAT_MESSAGE, ChatMessageEvent

PROCESS_NAME = "ingress-twitch-chat"


def _build_event(irc: IrcChatMessage) -> ChatMessageEvent:
    return ChatMessageEvent(
        schema_version=1,
        topic=TOPIC_CHAT_MESSAGE,
        platform="twitch",
        message_id=irc.message_id,
        author_name=irc.username,
        login=irc.login,
        author_id=irc.author_id,
        content=irc.content,
        timestamp=datetime.now(UTC).isoformat(),
        channel=irc.channel,
        raw={"source": "twitch_irc"},
    )


async def run(channel: str) -> None:
    connection = await connect_async(rabbitmq_url())
    mq_channel = await connection.channel()
    exchange = await declare_topic_exchange(mq_channel, stream_exchange())

    async def on_message(irc: IrcChatMessage) -> None:
        event = _build_event(irc)
        await publish_topic(exchange, TOPIC_CHAT_MESSAGE, event.to_dict())
        print(
            f"published {event.message_id[:8]} #{event.channel} {event.author_name}",
            flush=True,
        )

    print(
        f"Listening to #{channel.lstrip('#')} via anonymous IRC (no token required)",
        file=sys.stderr,
        flush=True,
    )
    await listen_anonymous_with_reconnect(channel, on_message)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Twitch IRC → RabbitMQ chat.message publisher")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
