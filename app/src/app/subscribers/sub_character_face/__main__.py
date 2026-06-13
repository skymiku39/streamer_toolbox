from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from app.processes.registry import register_subscriber
from bus.topology import DEFAULT_EXCHANGE, QUEUE_CHARACTER_FACE_CHARACTER_TURN

from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import (
    connect_blocking,
    consume_messages,
    publish_topic_blocking,
    setup_subscriber_queue,
)
from bus.topology import QUEUE_CHARACTER_FACE_CHARACTER_TURN
from events import TOPIC_CHARACTER_TURN

from sub_character_face.driver import build_driver
from sub_character_face.face import CharacterFace

PROCESS_NAME = "sub-character-face"


@register_subscriber(
    name="sub-character-face",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_CHARACTER_FACE_CHARACTER_TURN,
    description="character.turn → character.expression.ready",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Subscribe character.turn → character.expression.ready",
    )
    parser.add_argument(
        "--driver",
        default=os.environ.get("CHARACTER_FACE_DRIVER", "vts-stub"),
        choices=["vts", "vts-stub"],
        help="表情驅動：vts（WebSocket）或 vts-stub（離線 pass-through）",
    )
    args = parser.parse_args(argv)

    try:
        driver = build_driver(args.driver)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    exchange_name = stream_exchange()
    setup_subscriber_queue(
        channel,
        exchange_name=exchange_name,
        queue_name=QUEUE_CHARACTER_FACE_CHARACTER_TURN,
        routing_key=TOPIC_CHARACTER_TURN,
    )

    def publish(topic: str, payload: dict) -> None:
        publish_topic_blocking(
            channel,
            exchange_name=exchange_name,
            routing_key=topic,
            payload=payload,
        )
        turn_id = payload.get("turn_id", "")[:8]
        print(f"published {topic} turn_id={turn_id}", file=sys.stderr, flush=True)

    face = CharacterFace(driver=driver, publish=publish)

    print(
        f"{PROCESS_NAME} listening on {TOPIC_CHARACTER_TURN} driver={driver.name}",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_CHARACTER_FACE_CHARACTER_TURN, face.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
