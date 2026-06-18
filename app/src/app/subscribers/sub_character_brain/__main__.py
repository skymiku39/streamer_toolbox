from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from events import TOPIC_CHAT_MESSAGE

from app.processes.registry import register_subscriber
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import (
    connect_blocking,
    consume_messages,
    publish_topic_blocking,
    setup_subscriber_queue,
)
from bus.topology import DEFAULT_EXCHANGE, QUEUE_CHARACTER_BRAIN_CHAT_MESSAGE
from safety import BlocklistSafetyFilter
from streamer_config.paths import repo_root, resolve_path
from sub_character_brain.brain import CharacterBrain
from sub_character_brain.config import CharacterConfig
from sub_character_brain.llm import RuleBasedCharacterLlm

PROCESS_NAME = "sub-character-brain"
DEFAULT_CONFIG_PATH = repo_root() / "config" / "character_brain.json"


@register_subscriber(
    name="sub-character-brain",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_CHARACTER_BRAIN_CHAT_MESSAGE,
    description="chat.message → character.turn (+ optional chat.reply)",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Subscribe chat.message → character.turn (+ optional chat.reply)",
    )
    parser.add_argument(
        "--config",
        default=str(
            resolve_path("character_brain", legacy_default=DEFAULT_CONFIG_PATH)
        ),
        help="角色人設與觸發設定 JSON 路徑",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    config = CharacterConfig.load(config_path)
    safety = BlocklistSafetyFilter(
        blocklist=frozenset(
            word.lower() for word in (*config.input_blocklist, *config.output_blocklist)
        ),
    )

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    exchange_name = stream_exchange()
    setup_subscriber_queue(
        channel,
        exchange_name=exchange_name,
        queue_name=QUEUE_CHARACTER_BRAIN_CHAT_MESSAGE,
        routing_key=TOPIC_CHAT_MESSAGE,
    )

    def publish(topic: str, payload: dict) -> None:
        publish_topic_blocking(
            channel,
            exchange_name=exchange_name,
            routing_key=topic,
            payload=payload,
        )
        event_id = payload.get("turn_id") or payload.get("correlation_id", "")[:8]
        print(f"published {topic} id={event_id}", file=sys.stderr, flush=True)

    brain = CharacterBrain(
        config=config,
        llm=RuleBasedCharacterLlm(),
        safety=safety,
        publish=publish,
    )

    print(
        f"{PROCESS_NAME} listening on {TOPIC_CHAT_MESSAGE} "
        f"(trigger_prefix={config.trigger_prefix!r})",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_CHARACTER_BRAIN_CHAT_MESSAGE, brain.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
