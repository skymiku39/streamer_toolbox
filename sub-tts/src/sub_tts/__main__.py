from __future__ import annotations

import argparse
import os
import sys
import threading

from dotenv import load_dotenv

from pkg_bus.config import rabbitmq_url, stream_exchange
from pkg_bus.rabbitmq import connect_blocking, consume_messages, setup_subscriber_queue
from pkg_bus.topology import QUEUE_TTS_CHAT_MESSAGE
from pkg_events import TOPIC_CHAT_MESSAGE
from pkg_tts import create_tts_engine

from sub_tts.filter import MessageFilter, MessageFilterConfig
from sub_tts.queue_worker import TtsPlaybackQueue
from sub_tts.subscriber import ChatTtsSubscriber

PROCESS_NAME = "sub-tts"
STATS_INTERVAL_SECONDS = 30


def _parse_blacklist(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes"}


def build_filter_from_env(args: argparse.Namespace) -> MessageFilter:
    config = MessageFilterConfig(
        skip_commands=args.skip_commands,
        skip_urls=args.skip_urls,
        blacklist=_parse_blacklist(args.blacklist),
        max_length=args.max_length,
        template=args.template,
    )
    return MessageFilter(config)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Subscribe chat.message → TTS playback")
    parser.add_argument(
        "--engine",
        default=os.environ.get("TTS_ENGINE", "auto"),
        help="TTS backend: auto, noop, sapi5 (default: TTS_ENGINE or auto)",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=float(os.environ.get("TTS_COOLDOWN_SECONDS", "1.0")),
        help="Seconds between TTS utterances",
    )
    parser.add_argument(
        "--max-queue",
        type=int,
        default=int(os.environ.get("TTS_MAX_QUEUE_SIZE", "20")),
        help="Max queued utterances; oldest dropped when full",
    )
    parser.add_argument(
        "--skip-commands",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("TTS_SKIP_COMMANDS", True),
    )
    parser.add_argument(
        "--skip-urls",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("TTS_SKIP_URLS", True),
    )
    parser.add_argument(
        "--blacklist",
        default=os.environ.get("TTS_BLACKLIST", ""),
        help="Comma-separated blocked substrings",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=int(os.environ.get("TTS_MAX_LENGTH", "300")),
    )
    parser.add_argument(
        "--template",
        default=os.environ.get("TTS_TEMPLATE", "{author_name} 說 {content}"),
        help="Format string for spoken text",
    )
    args = parser.parse_args(argv)

    try:
        engine = create_tts_engine(args.engine)
    except (ValueError, RuntimeError) as exc:
        print(f"Failed to create TTS engine: {exc}", file=sys.stderr)
        return 1

    playback = TtsPlaybackQueue(
        engine,
        cooldown_seconds=args.cooldown,
        max_queue_size=args.max_queue,
    )
    subscriber = ChatTtsSubscriber(
        message_filter=build_filter_from_env(args),
        playback=playback,
    )

    stop_stats = threading.Event()

    def stats_loop() -> None:
        while not stop_stats.wait(STATS_INTERVAL_SECONDS):
            subscriber.log_stats()

    stats_thread = threading.Thread(target=stats_loop, daemon=True)
    stats_thread.start()

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    setup_subscriber_queue(
        channel,
        exchange_name=stream_exchange(),
        queue_name=QUEUE_TTS_CHAT_MESSAGE,
        routing_key=TOPIC_CHAT_MESSAGE,
    )

    print(
        f"{PROCESS_NAME}: engine={args.engine!r} cooldown={args.cooldown}s "
        f"max_queue={args.max_queue}",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_TTS_CHAT_MESSAGE, subscriber.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        stop_stats.set()
        playback.shutdown()
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
