from __future__ import annotations

import sys

from dotenv import load_dotenv

from app.processes.registry import register_subscriber
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import (
    connect_blocking,
    consume_messages,
    publish_topic_blocking,
    setup_subscriber_queue_bindings,
)
from bus.topology import DEFAULT_EXCHANGE, QUEUE_SUB_LIVE_STATUS
from events import TOPIC_CHAT_REPLY, TOPIC_STREAM_METADATA
from stream_store.idempotency import IdempotencyStore, default_idempotency_db_path

from sub_live_status.handler import LiveStatusSubscriber, NAMESPACE_STARTUP
from sub_live_status.status_messages import resolve_status_channel

PROCESS_NAME = "sub-live-status"


@register_subscriber(
    name="sub-live-status",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_SUB_LIVE_STATUS,
    description="stream.metadata → chat.reply 直播狀態宣告（不含 !ask）",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    connection = connect_blocking(rabbitmq_url())
    mq_channel = connection.channel()
    exchange_name = stream_exchange()
    setup_subscriber_queue_bindings(
        mq_channel,
        exchange_name=exchange_name,
        queue_name=QUEUE_SUB_LIVE_STATUS,
        routing_keys=[TOPIC_STREAM_METADATA],
    )

    def publish(topic: str, payload: dict) -> None:
        publish_topic_blocking(
            mq_channel,
            exchange_name=exchange_name,
            routing_key=topic,
            payload=payload,
        )
        if topic == TOPIC_CHAT_REPLY:
            preview = str(payload.get("content", ""))[:100]
            print(
                f"published {topic} correlation={payload.get('correlation_id', '')[:8]}: "
                f"{preview}",
                file=sys.stderr,
                flush=True,
            )

    idempotency = IdempotencyStore(default_idempotency_db_path())
    subscriber = LiveStatusSubscriber(publish=publish, idempotency=idempotency)

    print(
        f"{PROCESS_NAME} listening on {TOPIC_STREAM_METADATA} "
        f"(status-only, no !ask)",
        file=sys.stderr,
        flush=True,
    )

    twitch_channel = resolve_status_channel()
    try:
        consume_messages(mq_channel, QUEUE_SUB_LIVE_STATUS, subscriber.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        if subscriber._announced and twitch_channel:
            idempotency.release(NAMESPACE_STARTUP, twitch_channel.lower())
        idempotency.close()
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
