from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.processes.registry import register_subscriber
from bus.topology import DEFAULT_EXCHANGE, QUEUE_SUB_LLM

from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import (
    connect_blocking,
    consume_messages,
    publish_topic_blocking,
    setup_subscriber_queue_bindings,
)
from bus.topology import QUEUE_SUB_LLM
from events import TOPIC_CHAT_MESSAGE, TOPIC_CHAT_REPLY, TOPIC_STT_SEGMENT
from safety import BlocklistSafetyFilter

from sub_llm.config import LlmSubscriberConfig
from sub_llm.context_buffer import SttContextBuffer
from sub_llm.handler import LlmSubscriber
from sub_llm.factory import create_knowledge_store, create_llm_client

PROCESS_NAME = "sub-llm"
DEFAULT_CONFIG_PATH = "config/llm_subscriber.json"


def _load_config(config_path: Path | None) -> LlmSubscriberConfig:
    if config_path is not None and config_path.is_file():
        return LlmSubscriberConfig.load(config_path)
    return LlmSubscriberConfig.from_env()


@register_subscriber(
    name="sub-llm",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_SUB_LLM,
    description="chat.message + stt.segment → chat.reply (logic-llm)",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Subscribe chat.message + stt.segment → chat.reply",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("LLM_SUBSCRIBER_CONFIG", DEFAULT_CONFIG_PATH),
        help="觸發詞與安全設定 JSON 路徑（可選，缺省讀環境變數）",
    )
    parser.add_argument(
        "--llm-backend",
        default=os.environ.get("LLM_BACKEND", "template"),
        choices=["template", "openai", "gemini"],
        help="LLM 後端：template（佔位）、openai、gemini",
    )
    parser.add_argument(
        "--knowledge-path",
        default=os.environ.get("LLM_KNOWLEDGE_PATH", ""),
        help="知識庫檔案或目錄路徑（可選）",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    config = _load_config(config_path if config_path.is_file() else None)
    safety = BlocklistSafetyFilter(
        blocklist=frozenset(
            word.lower()
            for word in (*config.input_blocklist, *config.output_blocklist)
        ),
    )

    connection = connect_blocking(rabbitmq_url())
    channel = connection.channel()
    exchange_name = stream_exchange()
    setup_subscriber_queue_bindings(
        channel,
        exchange_name=exchange_name,
        queue_name=QUEUE_SUB_LLM,
        routing_keys=[TOPIC_CHAT_MESSAGE, TOPIC_STT_SEGMENT],
    )

    def publish(topic: str, payload: dict) -> None:
        publish_topic_blocking(
            channel,
            exchange_name=exchange_name,
            routing_key=topic,
            payload=payload,
        )
        correlation = payload.get("correlation_id", "")[:8]
        if topic == "chat.reply":
            preview = str(payload.get("content", ""))[:80]
            print(
                f"published {topic} correlation={correlation}: {preview}",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(f"published {topic} correlation={correlation}", file=sys.stderr, flush=True)

    try:
        llm = create_llm_client(args.llm_backend)
        knowledge = create_knowledge_store(args.knowledge_path or None)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    subscriber = LlmSubscriber(
        config=config,
        llm=llm,
        safety=safety,
        knowledge=knowledge,
        context_buffer=SttContextBuffer(window_minutes=config.context_window_minutes),
        publish=publish,
    )

    print(
        f"{PROCESS_NAME} listening on {TOPIC_CHAT_MESSAGE}, {TOPIC_STT_SEGMENT} "
        f"(backend={args.llm_backend!r}, triggers={config.trigger_prefixes!r})",
        file=sys.stderr,
        flush=True,
    )
    try:
        consume_messages(channel, QUEUE_SUB_LLM, subscriber.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
