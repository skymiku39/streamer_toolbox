from __future__ import annotations



import argparse

import os

import sys

import threading

from pathlib import Path



from dotenv import load_dotenv

from app.processes.registry import register_subscriber
from pkg_bus.topology import DEFAULT_EXCHANGE, QUEUE_CHARACTER_VOICE_TURN



from pkg_bus.config import rabbitmq_url, stream_exchange

from pkg_bus.rabbitmq import (

    connect_blocking,

    consume_messages,

    publish_topic_blocking,

    setup_subscriber_queue,

)

from pkg_bus.topology import QUEUE_CHARACTER_VOICE_TURN

from pkg_events import TOPIC_CHARACTER_TURN

from pkg_tts import create_voice_synthesizer



from sub_character_voice.voice import CharacterVoiceSubscriber



PROCESS_NAME = "sub-character-voice"

STATS_INTERVAL_SECONDS = 30





@register_subscriber(
    name="sub-character-voice",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_CHARACTER_VOICE_TURN,
    description="character.turn → TTS 合成 → character.audio.ready",
)
def main(argv: list[str] | None = None) -> int:

    load_dotenv()

    parser = argparse.ArgumentParser(

        description="Subscribe character.turn → synthesize audio → character.audio.ready",

    )

    parser.add_argument(

        "--engine",

        default=os.environ.get("VOICE_SYNTH_ENGINE", "auto"),

        help="Voice synthesizer backend: auto, file (default: VOICE_SYNTH_ENGINE or auto)",

    )

    parser.add_argument(

        "--output-dir",

        default=os.environ.get("VOICE_OUTPUT_DIR", "data/character_voice"),

        help="Directory for synthesized WAV files",

    )

    args = parser.parse_args(argv)



    try:

        synthesizer = create_voice_synthesizer(

            args.engine,

            output_dir=Path(args.output_dir),

        )

    except ValueError as exc:

        print(f"Failed to create voice synthesizer: {exc}", file=sys.stderr)

        return 1



    connection = connect_blocking(rabbitmq_url())

    channel = connection.channel()

    exchange_name = stream_exchange()

    setup_subscriber_queue(

        channel,

        exchange_name=exchange_name,

        queue_name=QUEUE_CHARACTER_VOICE_TURN,

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



    subscriber = CharacterVoiceSubscriber(synthesizer=synthesizer, publish=publish)



    stop_stats = threading.Event()



    def stats_loop() -> None:

        while not stop_stats.wait(STATS_INTERVAL_SECONDS):

            subscriber.log_stats()



    stats_thread = threading.Thread(target=stats_loop, daemon=True)

    stats_thread.start()



    print(

        f"{PROCESS_NAME} listening on {TOPIC_CHARACTER_TURN} "

        f"engine={args.engine!r} output_dir={args.output_dir}",

        file=sys.stderr,

        flush=True,

    )

    try:

        consume_messages(channel, QUEUE_CHARACTER_VOICE_TURN, subscriber.handle)

    except KeyboardInterrupt:

        print("Shutting down...", file=sys.stderr)

    finally:

        stop_stats.set()

        if connection.is_open:

            connection.close()

    return 0





if __name__ == "__main__":

    raise SystemExit(main())


