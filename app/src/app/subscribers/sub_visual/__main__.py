from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.processes.registry import register_subscriber
from bus.topology import DEFAULT_EXCHANGE, QUEUE_VISUAL_CHAT_MESSAGE

from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_blocking, consume_messages, setup_subscriber_queue
from bus.topology import QUEUE_VISUAL_CHAT_MESSAGE
from events import TOPIC_CHAT_MESSAGE, ChatMessageEvent

from sub_visual.config import SubtitleConfig
from sub_visual.service import SubtitleService

PROCESS_NAME = "sub-visual"


class VisualSubscriber:
    def __init__(self, service: SubtitleService, *, verbose: bool) -> None:
        self._service = service
        self._verbose = verbose
        self._count = 0
        self._filtered = 0

    def handle(self, payload: dict) -> None:
        event = ChatMessageEvent.from_dict(payload)
        update = self._service.handle_chat_message(event)
        if update is None:
            return

        if update.filtered:
            self._filtered += 1
            if self._verbose:
                print(
                    f"[filtered] {update.message_id[:8]} reason={update.filter_reason}",
                    file=sys.stderr,
                    flush=True,
                )
            return

        self._count += 1
        if self._verbose:
            print(
                f"[subtitle] {update.message_id[:8]} backend={update.backend} {update.text}",
                file=sys.stderr,
                flush=True,
            )

    @property
    def stats(self) -> tuple[int, int]:
        return self._count, self._filtered


@register_subscriber(
    name="sub-visual",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_VISUAL_CHAT_MESSAGE,
    description="chat.message → subtitle file / Spout2",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Subscribe chat.message → subtitle file or Spout2 output",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("VISUAL_CONFIG_PATH", "config/sub_visual.json"),
        help="字幕與過濾設定 JSON 路徑",
    )
    parser.add_argument(
        "--output-file",
        default=os.environ.get("VISUAL_OUTPUT_FILE"),
        help="覆寫 output_file（file 後端）",
    )
    parser.add_argument(
        "--backend",
        choices=["file", "spout2"],
        default=os.environ.get("VISUAL_BACKEND"),
        help="覆寫 backend",
    )
    parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("VISUAL_VERBOSE", "false").lower() in {"1", "true", "yes"},
    )
    args = parser.parse_args(argv)

    config = SubtitleConfig.from_json_path(Path(args.config))
    if args.output_file:
        config.output_file = args.output_file
    if args.backend:
        config.backend = args.backend

    service = SubtitleService(config)
    subscriber = VisualSubscriber(service, verbose=args.verbose)

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    setup_subscriber_queue(
        channel,
        exchange_name=stream_exchange(),
        queue_name=QUEUE_VISUAL_CHAT_MESSAGE,
        routing_key=TOPIC_CHAT_MESSAGE,
    )

    print(
        f"[{PROCESS_NAME}] backend={service.sender.backend_name} "
        f"output={config.output_file} queue={QUEUE_VISUAL_CHAT_MESSAGE}",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_VISUAL_CHAT_MESSAGE, subscriber.handle)
    except KeyboardInterrupt:
        written, filtered = subscriber.stats
        print(
            f"Shutting down... written={written} filtered={filtered}",
            file=sys.stderr,
            flush=True,
        )
    finally:
        service.close()
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
