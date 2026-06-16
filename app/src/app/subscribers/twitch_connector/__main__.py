from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from events import TOPIC_CHAT_REPLY, TOPIC_SYSTEM_ERROR

from app.processes.registry import register_subscriber
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import (
    connect_blocking,
    consume_messages,
    publish_topic_blocking,
    setup_subscriber_queue,
)
from bus.topology import DEFAULT_EXCHANGE, QUEUE_TWITCH_CONNECTOR_CHAT_REPLY
from identity_oauth import SyncEnvTokenProvider
from stream_store.idempotency import IdempotencyStore, default_idempotency_db_path
from twitch_connector.dispatcher import ChatReplyDispatcher
from twitch_connector.subscriber import ReplySubscriber
from twitch_connector.throttle import MessageThrottle
from twitch_connector.twitch_sender import TwitchChatSender

PROCESS_NAME = "twitch-connector"


@register_subscriber(
    name="twitch-connector",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_TWITCH_CONNECTOR_CHAT_REPLY,
    description="chat.reply → Twitch Helix 發話（Egress）",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Subscribe chat.reply → Twitch Helix send (egress connector)"
    )
    parser.add_argument(
        "--window-limit",
        type=int,
        default=int(os.environ.get("TWITCH_SEND_WINDOW_LIMIT", "20")),
        help="Global send window limit (default: 20 per 30s)",
    )
    parser.add_argument(
        "--per-channel-interval",
        type=float,
        default=float(os.environ.get("TWITCH_SEND_PER_CHANNEL_INTERVAL", "1.0")),
        help="Minimum seconds between sends to the same channel",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=int(os.environ.get("TWITCH_SEND_MAX_RETRIES", "3")),
    )
    args = parser.parse_args(argv)

    token_provider = SyncEnvTokenProvider(role="bot")
    try:
        token_provider.validate()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    throttle = MessageThrottle(
        window_limit=args.window_limit,
        per_channel_interval_seconds=args.per_channel_interval,
    )
    twitch_sender = TwitchChatSender(token_provider, throttle=throttle)
    dispatcher = ChatReplyDispatcher(senders={"twitch": twitch_sender})

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    exchange_name = stream_exchange()
    setup_subscriber_queue(
        channel,
        exchange_name=exchange_name,
        queue_name=QUEUE_TWITCH_CONNECTOR_CHAT_REPLY,
        routing_key=TOPIC_CHAT_REPLY,
    )

    def publish_error(payload: dict) -> None:
        publish_topic_blocking(
            channel,
            exchange_name=exchange_name,
            routing_key=TOPIC_SYSTEM_ERROR,
            payload=payload,
        )

    idempotency = IdempotencyStore(default_idempotency_db_path())
    subscriber = ReplySubscriber(
        dispatcher,
        publish_error=publish_error,
        max_retries=args.max_retries,
        idempotency=idempotency,
    )

    print(
        f"Listening for {TOPIC_CHAT_REPLY} → Twitch Helix "
        f"(queue={QUEUE_TWITCH_CONNECTOR_CHAT_REPLY})",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_TWITCH_CONNECTOR_CHAT_REPLY, subscriber.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        idempotency.close()
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
