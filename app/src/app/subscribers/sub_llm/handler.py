from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from events import (
    SOURCE_LOGIC_LLM,
    TOPIC_CHAT_MESSAGE,
    TOPIC_CHAT_REPLY,
    TOPIC_STT_SEGMENT,
    ChatMessageEvent,
    ChatReplyEvent,
    SttSegmentEvent,
)
from safety import SafetyFilter
from safety.stt_input import is_hallucination_text

from sub_llm.config import LlmSubscriberConfig
from sub_llm.context_buffer import SttContextBuffer
from sub_llm.knowledge import KnowledgeStore
from sub_llm.llm import LlmClient
from sub_llm.triggers import TriggerMatcher

BUSY_REPLY = "⏳ 上一個問題還在處理中，請稍後再試。"


class LlmSubscriber:
    def __init__(
        self,
        config: LlmSubscriberConfig,
        llm: LlmClient,
        safety: SafetyFilter,
        knowledge: KnowledgeStore,
        context_buffer: SttContextBuffer,
        publish: Callable[[str, dict[str, Any]], None],
    ) -> None:
        self._config = config
        self._llm = llm
        self._safety = safety
        self._knowledge = knowledge
        self._context_buffer = context_buffer
        self._publish = publish
        self._triggers = TriggerMatcher(tuple(config.trigger_prefixes))
        self._busy = threading.Lock()

    def handle(self, payload: dict[str, Any]) -> None:
        topic = payload.get("topic")
        if topic == TOPIC_STT_SEGMENT:
            self._handle_stt_segment(payload)
        elif topic == TOPIC_CHAT_MESSAGE:
            self._handle_chat_message(payload)

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
        question = self._triggers.extract_question(event.content)
        if question is None:
            return

        filtered_question = self._safety.filter_input(question)
        if filtered_question is None:
            return

        if not self._busy.acquire(blocking=False):
            self._publish_reply(event, BUSY_REPLY)
            return

        try:
            context = self._context_buffer.context_text()
            knowledge = self._knowledge.query(filtered_question)
            raw_reply = self._llm.ask(
                filtered_question,
                context=context,
                knowledge=knowledge,
            )
            filtered_reply = self._safety.filter_output(raw_reply)
            if filtered_reply is None:
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
