from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from events import (
    TOPIC_CHARACTER_AUDIO_READY,
    TOPIC_CHARACTER_EXPRESSION_READY,
    CharacterAudioReadyEvent,
    CharacterExpressionReadyEvent,
)

from app.processes.registry import register_subscriber
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_blocking, consume_messages, setup_subscriber_queue_multi
from bus.topology import DEFAULT_EXCHANGE, QUEUE_CHARACTER_STAGE
from sub_character_stage.coordinator import TurnCoordinator
from sub_character_stage.driver import create_stage_driver

PROCESS_NAME = "sub-character-stage"
DEFAULT_MERGE_TIMEOUT_SEC = 5.0


class CharacterStageSubscriber:
    def __init__(self, coordinator: TurnCoordinator) -> None:
        self._coordinator = coordinator
        self._audio_count = 0
        self._expression_count = 0

    def handle(self, payload: dict) -> None:
        topic = payload.get("topic")
        if topic == TOPIC_CHARACTER_AUDIO_READY:
            event = CharacterAudioReadyEvent.from_dict(payload)
            self._audio_count += 1
            self._coordinator.handle_audio(event)
            return
        if topic == TOPIC_CHARACTER_EXPRESSION_READY:
            event = CharacterExpressionReadyEvent.from_dict(payload)
            self._expression_count += 1
            self._coordinator.handle_expression(event)
            return
        raise ValueError(f"unexpected topic on character stage queue: {topic!r}")

    @property
    def stats(self) -> tuple[int, int]:
        return self._audio_count, self._expression_count


@register_subscriber(
    name="sub-character-stage",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_CHARACTER_STAGE,
    description="character audio + expression → OBS stage sync",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Subscribe character.audio.ready + character.expression.ready → OBS stage",
    )
    parser.add_argument(
        "--driver",
        choices=["log", "obs"],
        default=os.environ.get("STAGE_DRIVER", "log"),
        help="舞台輸出 driver（log 或 obs WebSocket）",
    )
    parser.add_argument(
        "--merge-timeout",
        type=float,
        default=float(os.environ.get("STAGE_MERGE_TIMEOUT_SEC", DEFAULT_MERGE_TIMEOUT_SEC)),
        help="等待 expression 就緒秒數，逾時則僅播 audio",
    )
    parser.add_argument(
        "--obs-host",
        default=os.environ.get("OBS_WS_HOST", "localhost"),
    )
    parser.add_argument(
        "--obs-port",
        type=int,
        default=int(os.environ.get("OBS_WS_PORT", "4455")),
    )
    parser.add_argument(
        "--obs-password",
        default=os.environ.get("OBS_WS_PASSWORD", ""),
    )
    parser.add_argument(
        "--obs-scene",
        default=os.environ.get("OBS_SCENE_NAME", ""),
        help="切換至的 Program 場景（空字串則不切換）",
    )
    parser.add_argument(
        "--obs-media-source",
        default=os.environ.get("OBS_MEDIA_SOURCE", "CharacterAudio"),
        help="播放音檔的 Media Source 名稱",
    )
    args = parser.parse_args(argv)

    driver = create_stage_driver(
        args.driver,
        obs_host=args.obs_host,
        obs_port=args.obs_port,
        obs_password=args.obs_password,
        obs_scene=args.obs_scene,
        obs_media_source=args.obs_media_source,
    )
    coordinator = TurnCoordinator(driver, merge_timeout_sec=args.merge_timeout)
    subscriber = CharacterStageSubscriber(coordinator)

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    setup_subscriber_queue_multi(
        channel,
        exchange_name=stream_exchange(),
        queue_name=QUEUE_CHARACTER_STAGE,
        routing_keys=[
            TOPIC_CHARACTER_AUDIO_READY,
            TOPIC_CHARACTER_EXPRESSION_READY,
        ],
    )

    print(
        f"[{PROCESS_NAME}] driver={args.driver} merge_timeout={args.merge_timeout}s "
        f"queue={QUEUE_CHARACTER_STAGE}",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_CHARACTER_STAGE, subscriber.handle)
    except KeyboardInterrupt:
        audio_count, expression_count = subscriber.stats
        print(
            f"Shutting down... audio={audio_count} expression={expression_count}",
            file=sys.stderr,
            flush=True,
        )
    finally:
        coordinator.close()
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
