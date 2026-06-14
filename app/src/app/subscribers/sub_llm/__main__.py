from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.processes.registry import register_subscriber
from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import (
    connect_blocking,
    consume_messages,
    publish_topic_blocking,
    setup_subscriber_queue_bindings,
)
from bus.topology import DEFAULT_EXCHANGE, QUEUE_SUB_LLM
from events import TOPIC_CHAT_MESSAGE, TOPIC_CHAT_REPLY, TOPIC_STT_SEGMENT, TOPIC_STREAM_METADATA
from safety import BlocklistSafetyFilter
from stream_store.idempotency import IdempotencyStore, default_idempotency_db_path

from sub_llm.config import LlmSubscriberConfig
from sub_llm.context_buffer import LiveContextBuffer
from sub_llm.handler import LlmSubscriber
from sub_llm.factory import create_knowledge_store, create_llm_client, preload_knowledge_store
from sub_llm.game_context import create_game_info_provider
from sub_llm.startup_announcement import publish_startup_announcement, resolve_announcement_channel

PROCESS_NAME = "sub-llm"
DEFAULT_CONFIG_PATH = "config/llm_subscriber.json"
NAMESPACE_STARTUP = "sub_llm.startup"


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
    os.environ.setdefault("LLM_MAX_REPLY_LENGTH", str(config.reply_max_length))
    safety = BlocklistSafetyFilter(
        blocklist=frozenset(
            word.lower()
            for word in (*config.input_blocklist, *config.output_blocklist)
        ),
    )

    connection = connect_blocking(rabbitmq_url())
    mq_channel = connection.channel()
    exchange_name = stream_exchange()
    setup_subscriber_queue_bindings(
        mq_channel,
        exchange_name=exchange_name,
        queue_name=QUEUE_SUB_LLM,
        routing_keys=[TOPIC_CHAT_MESSAGE, TOPIC_STT_SEGMENT, TOPIC_STREAM_METADATA],
    )

    def publish(topic: str, payload: dict) -> None:
        publish_topic_blocking(
            mq_channel,
            exchange_name=exchange_name,
            routing_key=topic,
            payload=payload,
        )
        correlation = payload.get("correlation_id", "")[:8]
        if topic == TOPIC_CHAT_REPLY:
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
        preload_knowledge_store(knowledge)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    web_search = (os.environ.get("LLM_WEB_SEARCH", "true") or "true").strip().lower()
    print(
        f"[sub-llm] llm_client={type(llm).__name__} "
        f"backend={args.llm_backend!r} web_search={web_search!r}",
        file=sys.stderr,
        flush=True,
    )

    bot_author_id = (os.environ.get("TWITCH_BOT_ID") or "").strip()
    bot_login = (os.environ.get("TWITCH_BOT_LOGIN") or "").strip().lower()
    skip_author_ids = frozenset({bot_author_id}) if bot_author_id else frozenset()
    skip_logins = frozenset({bot_login}) if bot_login else frozenset()

    idempotency = IdempotencyStore(default_idempotency_db_path())
    game_info = create_game_info_provider()
    game_info_mode = "igdb" if game_info is not None else "disabled"
    context_buffer = LiveContextBuffer(
        window_minutes=config.context_window_minutes,
        skip_author_ids=skip_author_ids,
        bot_reply_window_minutes=config.bot_reply_window_minutes,
        bot_reply_max_pairs=config.bot_reply_max_pairs,
    )
    subscriber = LlmSubscriber(
        config=config,
        llm=llm,
        safety=safety,
        knowledge=knowledge,
        context_buffer=context_buffer,
        publish=publish,
        idempotency=idempotency,
        game_info=game_info,
        skip_trigger_author_ids=skip_author_ids,
        skip_trigger_logins=skip_logins,
    )

    print(
        f"{PROCESS_NAME} listening on {TOPIC_CHAT_MESSAGE}, {TOPIC_STT_SEGMENT}, "
        f"{TOPIC_STREAM_METADATA} "
        f"(backend={args.llm_backend!r}, qa_memory_mode={config.qa_memory_mode!r}, "
        f"knowledge=RAG/chroma, "
        f"game_info={game_info_mode!r}, triggers={config.trigger_prefixes!r})",
        file=sys.stderr,
        flush=True,
    )
    twitch_channel = resolve_announcement_channel()
    startup_claimed = False
    if twitch_channel and idempotency.claim(NAMESPACE_STARTUP, twitch_channel.lower()):
        startup_claimed = True
        publish_startup_announcement(
            llm=llm,
            safety=safety,
            config=config,
            publish=publish,
            context_buffer=context_buffer,
            backend=args.llm_backend,
        )
    elif twitch_channel:
        print(
            "[sub-llm] startup announcement skipped: duplicate sub-llm instance",
            file=sys.stderr,
            flush=True,
        )
    try:
        consume_messages(mq_channel, QUEUE_SUB_LLM, subscriber.handle)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        if startup_claimed and twitch_channel:
            idempotency.release(NAMESPACE_STARTUP, twitch_channel.lower())
        idempotency.close()
        if connection.is_open:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
