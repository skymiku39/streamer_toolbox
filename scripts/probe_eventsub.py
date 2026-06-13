"""EventSub 訂閱探測：啟動 bot、等待 setup_hook 完成後回報訂閱狀態。"""
from __future__ import annotations

import asyncio
import logging
import sys

from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from identity_oauth import MultiAccountTokenProvider
from ingress_twitch_eventsub.bot import EventSubIngressBot
from ingress_twitch_eventsub.chat_status import CHAT_INGRESS_EVENTSUB, CHAT_INGRESS_STATUS_PREFIX
from ingress_twitch_eventsub.publisher import MqEventPublisher
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_async, declare_topic_exchange


class _NoOpPublisher:
    async def publish_chat(self, event) -> None:  # noqa: ANN001
        pass

    async def publish_eventsub(self, topic: str, payload: dict) -> None:
        pass


async def probe(channel: str, *, wait_seconds: float = 25.0) -> int:
    token_provider = MultiAccountTokenProvider()
    channel_creds = await token_provider.get_credentials("channel")
    bot_creds = await token_provider.get_credentials("bot")

    connection = await connect_async(rabbitmq_url())
    mq_channel = await connection.channel()
    exchange = await declare_topic_exchange(mq_channel, stream_exchange())
    publisher = MqEventPublisher(exchange)

    normalized = channel.lstrip("#")
    bot = EventSubIngressBot(
        client_id=channel_creds.client_id,
        client_secret=channel_creds.client_secret,
        bot_id=bot_creds.bot_id,
        token=bot_creds.access_token,
        refresh_token=bot_creds.refresh_token,
        channel_token=channel_creds.access_token,
        channel_refresh_token=channel_creds.refresh_token,
        channels=[normalized],
        broadcaster_id=channel_creds.broadcaster_id,
        broadcaster_type=channel_creds.broadcaster_type,
        publisher=publisher,
    )

    start_task = asyncio.create_task(bot.start())
    try:
        try:
            await asyncio.wait_for(bot.wait_until_ready(), timeout=wait_seconds)
        except TimeoutError:
            print("=== EventSub Probe Result ===")
            print("ERROR: bot.wait_until_ready() timed out")
            return 1
        await asyncio.sleep(1.0)

        failed = [(entry[0], entry[4]) for entry in bot._failed_subs]
        print("=== EventSub Probe Result ===")
        print(f"channel={normalized}")
        print(f"chat_read_ok={bot.chat_read_ok}")
        print(f"failed_count={len(failed)}")
        for name, token_owner in failed:
            print(f"  FAILED: {name} (token_owner={token_owner})")
        if bot.chat_read_ok:
            print(f"{CHAT_INGRESS_STATUS_PREFIX}{CHAT_INGRESS_EVENTSUB}")
        return 0 if bot.chat_read_ok and not failed else 1
    finally:
        await bot.close()
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass
        if connection.is_closed is False:
            await connection.close()


def main() -> int:
    import os

    channel = (os.environ.get("TWITCH_CHANNEL") or "").strip()
    if not channel:
        print("TWITCH_CHANNEL required", file=sys.stderr)
        return 1
    return asyncio.run(probe(channel))


if __name__ == "__main__":
    raise SystemExit(main())
