from __future__ import annotations

import argparse
import os
import sys
import threading
from pathlib import Path

import pika
from dotenv import load_dotenv
from events import (
    TOPIC_CHAT_MESSAGE,
    TOPIC_CHAT_REPLY,
    TOPIC_CONFIG_CHANGED,
    TOPIC_EVENTSUB_PREFIX,
    ConfigChangedEvent,
)

from app.processes.registry import register_subscriber
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import (
    connect_blocking,
    consume_messages,
    publish_topic_blocking,
    setup_subscriber_queue_multi,
)
from bus.topology import DEFAULT_EXCHANGE, QUEUE_BOT_LOGIC_INBOX
from control import MODULE_RULE_BOT, active_profile_id
from streamer_config.paths import resolve_path
from sub_bot_logic.redemption_map import RedemptionResponseMap
from sub_bot_logic.response_map import BotResponseMap
from sub_bot_logic.rules_engine import BotRulesEngine

PROCESS_NAME = "sub-bot-logic"
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESPONSES = _REPO_ROOT / "config" / "examples" / "bot_responses.example.json"
DEFAULT_REDEMPTIONS = _REPO_ROOT / "config" / "examples" / "redemption_responses.example.json"


class BotLogicSubscriber:
    def __init__(
        self,
        engine: BotRulesEngine,
        *,
        exchange_name: str,
        channel: pika.adapters.blocking_connection.BlockingChannel,
    ) -> None:
        self._engine = engine
        self._exchange_name = exchange_name
        self._channel = channel
        self._reply_count = 0
        self._lock = threading.Lock()

    def handle(self, payload: dict) -> None:
        topic = payload.get("topic")
        if topic == TOPIC_CONFIG_CHANGED:
            self._handle_config_changed(payload)
            return
        reply = self._engine.process_payload(payload)
        if reply is None:
            return
        publish_topic_blocking(
            self._channel,
            exchange_name=self._exchange_name,
            routing_key=TOPIC_CHAT_REPLY,
            payload=reply.to_dict(),
        )
        with self._lock:
            self._reply_count += 1
        print(
            f"[reply] [{reply.source}] #{reply.channel}: {reply.content[:80]}",
            flush=True,
        )

    def stats_loop(self, stop: threading.Event) -> None:
        while not stop.wait(30):
            with self._lock:
                count = self._reply_count
            print(f"[stats] replies_published={count}", file=sys.stderr, flush=True)

    def _handle_config_changed(self, payload: dict) -> None:
        try:
            event = ConfigChangedEvent.from_dict(payload)
        except (KeyError, TypeError, ValueError):
            return
        if event.module_id != MODULE_RULE_BOT:
            return
        if event.profile_id != active_profile_id():
            return
        with self._lock:
            self._engine.reload()
        print(
            f"[{PROCESS_NAME}] reloaded config ({event.config_file})",
            file=sys.stderr,
            flush=True,
        )


@register_subscriber(
    name="sub-bot-logic",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_BOT_LOGIC_INBOX,
    description="chat.message + eventsub.* → chat.reply",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Subscribe chat.message + eventsub.* → publish chat.reply"
    )
    parser.add_argument(
        "--responses",
        default=str(
            resolve_path("bot_responses", legacy_default=DEFAULT_RESPONSES)
        ),
        help="bot_responses.json 路徑",
    )
    parser.add_argument(
        "--redemptions",
        default=str(
            resolve_path("redemption_responses", legacy_default=DEFAULT_REDEMPTIONS)
        ),
        help="redemption_responses.json 路徑",
    )
    parser.add_argument(
        "--command-prefix",
        default=os.environ.get("BOT_COMMAND_PREFIX", "!"),
    )
    parser.add_argument(
        "--bot-identity",
        default=os.environ.get("BOT_IDENTITY", "Streamer Toolbox Bot"),
    )
    args = parser.parse_args(argv)

    engine = BotRulesEngine(
        BotResponseMap(args.responses),
        RedemptionResponseMap(args.redemptions),
        command_prefix=args.command_prefix,
        bot_identity=args.bot_identity,
    )

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    exchange = stream_exchange()
    setup_subscriber_queue_multi(
        channel,
        exchange_name=exchange,
        queue_name=QUEUE_BOT_LOGIC_INBOX,
        routing_keys=[TOPIC_CHAT_MESSAGE, f"{TOPIC_EVENTSUB_PREFIX}#", TOPIC_CONFIG_CHANGED],
    )

    subscriber = BotLogicSubscriber(engine, exchange_name=exchange, channel=channel)
    stop_stats = threading.Event()
    stats_thread = threading.Thread(
        target=subscriber.stats_loop,
        args=(stop_stats,),
        daemon=True,
    )
    stats_thread.start()

    print(
        f"{PROCESS_NAME} listening on {TOPIC_CHAT_MESSAGE} + {TOPIC_EVENTSUB_PREFIX}# + "
        f"{TOPIC_CONFIG_CHANGED}",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_BOT_LOGIC_INBOX, subscriber.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        stop_stats.set()
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
