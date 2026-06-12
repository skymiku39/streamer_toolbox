from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

from ingress_yt_read.publisher import run_publisher
from pkg_bus.config import rabbitmq_url, stream_exchange
from pkg_bus.rabbitmq import connect_async, declare_topic_exchange, publish_topic
from pkg_events import TOPIC_CHAT_MESSAGE

PROCESS_NAME = "ingress-yt-read"


def _resolve_video(*, cli_video: str) -> str:
    for candidate in (cli_video, os.environ.get("YT_CHANNEL", ""), os.environ.get("YT_VIDEO", "")):
        value = (candidate or "").strip()
        if value:
            return value
    return ""


async def run(video: str) -> None:
    connection = await connect_async(rabbitmq_url())
    mq_channel = await connection.channel()
    exchange = await declare_topic_exchange(mq_channel, stream_exchange())

    async def publish(payload: dict) -> None:
        await publish_topic(exchange, TOPIC_CHAT_MESSAGE, payload)
        message_id = payload.get("message_id", "")[:8]
        author = payload.get("author_name", "")
        ch = payload.get("channel", "")
        print(f"published {message_id} #{ch} {author}", flush=True)

    print(
        f"Listening to YouTube live chat ({video}) via tubechat_lens",
        file=sys.stderr,
        flush=True,
    )

    try:
        await run_publisher(video, publish)
    finally:
        await connection.close()


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="YouTube live chat (tubechat_lens) → RabbitMQ chat.message publisher",
    )
    parser.add_argument(
        "--video",
        default="",
        help="YouTube 直播網址或 11 碼影片 ID（亦可設 YT_CHANNEL / YT_VIDEO）",
    )
    args = parser.parse_args(argv)

    video = _resolve_video(cli_video=args.video)
    if not video:
        print("YT_CHANNEL, YT_VIDEO must be set or pass --video", file=sys.stderr)
        return 1

    try:
        asyncio.run(run(video))
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
