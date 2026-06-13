from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from events import (
    SOURCE_LOGIC_LLM,
    TOPIC_CHAT_MESSAGE,
    TOPIC_CHAT_REPLY,
    TOPIC_STT_SEGMENT,
    TOPIC_STREAM_METADATA,
    ChatMessageEvent,
    ChatReplyEvent,
    SttSegmentEvent,
    StreamMetadataEvent,
)
from safety import SafetyFilter
from safety.stt_input import is_hallucination_text
from stream_store.idempotency import IdempotencyStore

from sub_llm.chat_format import plain_text_for_chat
from sub_llm.config import LlmSubscriberConfig
from sub_llm.context_buffer import LiveContextBuffer
from sub_llm.knowledge import KnowledgeStore
from sub_llm.llm import LlmClient
from sub_llm.triggers import TriggerMatcher

BUSY_REPLY = "⏳ 上一個問題還在處理中，請稍後再試。"
NAMESPACE_CHAT_TRIGGER = "sub_llm.chat.trigger"
NAMESPACE_ASK_CONTENT = "sub_llm.chat.ask_content"
ASK_CONTENT_DEDUP_WINDOW_SECONDS = 120


def _ask_content_dedup_key(event: ChatMessageEvent, question: str) -> str:
    bucket = int(time.time()) // ASK_CONTENT_DEDUP_WINDOW_SECONDS
    channel = (event.channel or "").strip().lower()
    author = (event.author_id or event.login or event.author_name or "").strip().lower()
    return f"{bucket}:{channel}:{author}:{question.strip().lower()}"


class LlmSubscriber:
    def __init__(
        self,
        config: LlmSubscriberConfig,
        llm: LlmClient,
        safety: SafetyFilter,
        knowledge: KnowledgeStore,
        context_buffer: LiveContextBuffer,
        publish: Callable[[str, dict[str, Any]], None],
        *,
        idempotency: IdempotencyStore | None = None,
    ) -> None:
        self._config = config
        self._llm = llm
        self._safety = safety
        self._knowledge = knowledge
        self._context_buffer = context_buffer
        self._publish = publish
        self._idempotency = idempotency
        self._triggers = TriggerMatcher(tuple(config.trigger_prefixes))
        self._busy = threading.Lock()

    def handle(self, payload: dict[str, Any]) -> None:
        topic = payload.get("topic")
        if topic == TOPIC_STT_SEGMENT:
            self._handle_stt_segment(payload)
        elif topic == TOPIC_STREAM_METADATA:
            self._handle_stream_metadata(payload)
        elif topic == TOPIC_CHAT_MESSAGE:
            self._handle_chat_message(payload)

    def _handle_stream_metadata(self, payload: dict[str, Any]) -> None:
        event = StreamMetadataEvent.from_dict(payload)
        self._context_buffer.update_stream_metadata(event)
        game = event.game_name or "-"
        title_preview = (event.title or "-")[:40]
        print(
            f"[sub-llm] stream.metadata live={event.is_live} "
            f"game={game} title={title_preview}",
            file=sys.stderr,
            flush=True,
        )

    def _handle_stt_segment(self, payload: dict[str, Any]) -> None:
        event = SttSegmentEvent.from_dict(payload)
        if is_hallucination_text(event.text):
            return
        filtered = self._safety.filter_input(event.text)
        if filtered is None:
            return
        self._context_buffer.add_segment(event)

    def _handle_chat_message(self, payload: dict[str, Any]) -> None:
        event = ChatMessageEvent.from_dict(payload)
        self._context_buffer.add_chat_message(event)

        question = self._triggers.extract_question(event.content)
        if question is None:
            return

        filtered_question = self._safety.filter_input(question)
        if filtered_question is None:
            return

        if self._idempotency is not None:
            content_key = _ask_content_dedup_key(event, filtered_question)
            if not self._idempotency.claim(NAMESPACE_ASK_CONTENT, content_key):
                print(
                    f"[sub-llm] skip duplicate ask content message_id={event.message_id[:8]}",
                    file=sys.stderr,
                    flush=True,
                )
                return

        if self._idempotency is not None and not self._idempotency.claim(
            NAMESPACE_CHAT_TRIGGER,
            event.message_id,
        ):
            print(
                f"[sub-llm] skip duplicate trigger message_id={event.message_id[:8]}",
                file=sys.stderr,
                flush=True,
            )
            return

        if not self._busy.acquire(blocking=False):
            self._publish_reply(event, BUSY_REPLY)
            return

        try:
            channel = event.channel or ""
            context = self._context_buffer.context_text(channel)
            stt_count, chat_count, context_len, has_stream = self._context_buffer.stats(channel)
            print(
                f"[sub-llm] context stream={has_stream} stt={stt_count} "
                f"chat={chat_count} chars={context_len}",
                file=sys.stderr,
                flush=True,
            )
            if not has_stream:
                print(
                    "[sub-llm] 警告：尚無 stream.metadata。"
                    "請在另一終端執行 "
                    "`uv run python -m app.main run --stack ingress`",
                    file=sys.stderr,
                    flush=True,
                )
            knowledge = self._knowledge.query(filtered_question, channel=channel)
            raw_reply = self._llm.ask(
                filtered_question,
                context=context,
                knowledge=knowledge,
            )
            filtered_reply = self._safety.filter_output(raw_reply)
            if filtered_reply is None:
                return
            filtered_reply = plain_text_for_chat(filtered_reply)
            if not filtered_reply:
                return
            if len(filtered_reply) > self._config.reply_max_length:
                limit = self._config.reply_max_length
                filtered_reply = filtered_reply[: limit - 3] + "..."
            self._publish_reply(event, filtered_reply)
        finally:
            self._busy.release()

    def _publish_reply(self, trigger: ChatMessageEvent, content: str) -> None:
        reply = ChatReplyEvent(
            schema_version=1,
            topic=TOPIC_CHAT_REPLY,
            platform=trigger.platform,
            channel=trigger.channel or "",
            content=content,
            reply_to_message_id=trigger.message_id,
            sender="bot",
            source=SOURCE_LOGIC_LLM,
            correlation_id=trigger.message_id,
        )
        self._publish(TOPIC_CHAT_REPLY, reply.to_dict())
