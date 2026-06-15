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
    TOPIC_MEMORY_QA_RECORD,
    TOPIC_STT_SEGMENT,
    TOPIC_STREAM_METADATA,
    ChatMessageEvent,
    ChatReplyEvent,
    MemoryQaRecordEvent,
    SttSegmentEvent,
    StreamMetadataEvent,
)
from safety import SafetyFilter
from safety.stt_input import is_hallucination_text
from stream_store import StreamTextStore
from stream_store.idempotency import IdempotencyStore

from game_info import GameInfoProvider

from sub_llm.chat_format import cap_reply_for_chat, cap_reply_for_twitch, plain_text_for_chat
from sub_llm.config import TWITCH_CHAT_MAX_CHARS, LlmSubscriberConfig
from sub_llm.context_buffer import LiveContextBuffer
from sub_llm.game_context import build_game_reference, resolve_live_game_name
from sub_llm.knowledge import KnowledgeStore
from sub_llm.live_activity import current_activity_context_hint, is_current_activity_question
from sub_llm.llm import LlmClient
from sub_llm.qa_memory_gate import should_persist_qa_memory
from sub_llm.session_recap import build_session_recap_reference
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


def _is_skipped_trigger_author(
    event: ChatMessageEvent,
    skip_author_ids: frozenset[str],
    skip_logins: frozenset[str],
) -> bool:
    if skip_author_ids:
        author_id = (event.author_id or "").strip()
        if author_id and author_id in skip_author_ids:
            return True
    if skip_logins:
        login = (event.login or event.author_name or "").strip().lower()
        if login and login in skip_logins:
            return True
    return False


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
        game_info: GameInfoProvider | None = None,
        stream_store: StreamTextStore | None = None,
        skip_trigger_author_ids: frozenset[str] = frozenset(),
        skip_trigger_logins: frozenset[str] = frozenset(),
    ) -> None:
        self._config = config
        self._llm = llm
        self._safety = safety
        self._knowledge = knowledge
        self._context_buffer = context_buffer
        self._publish = publish
        self._idempotency = idempotency
        self._game_info = game_info
        self._stream_store = stream_store
        self._skip_trigger_author_ids = skip_trigger_author_ids
        self._skip_trigger_logins = skip_trigger_logins
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
        if not self._context_buffer.update_stream_metadata(event):
            return
        game = event.game_name or "-"
        title_preview = (event.title or "-")[:40]
        print(
            f"stream metadata updated live={event.is_live} "
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

        if event.platform == "youtube":
            # #region agent log
            import json
            import time
            from pathlib import Path

            Path("debug-5542a6.log").open("a", encoding="utf-8").write(
                json.dumps(
                    {
                        "sessionId": "5542a6",
                        "hypothesisId": "E",
                        "location": "handler.py:_handle_chat_message",
                        "message": "youtube !ask trigger seen",
                        "data": {
                            "channel": event.channel,
                            "message_id": (event.message_id or "")[:12],
                        },
                        "timestamp": int(time.time() * 1000),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            # #endregion

        if _is_skipped_trigger_author(
            event,
            self._skip_trigger_author_ids,
            self._skip_trigger_logins,
        ):
            print(
                f"[sub-llm] skip bot trigger message_id={event.message_id[:8]}",
                file=sys.stderr,
                flush=True,
            )
            return

        filtered_question = self._safety.filter_input(question)
        if filtered_question is None:
            return

        content_key: str | None = None
        content_claimed = False
        trigger_claimed = False
        if self._idempotency is not None:
            content_key = _ask_content_dedup_key(event, filtered_question)
            if not self._idempotency.claim(NAMESPACE_ASK_CONTENT, content_key):
                print(
                    f"[sub-llm] skip duplicate ask content message_id={event.message_id[:8]}",
                    file=sys.stderr,
                    flush=True,
                )
                return
            content_claimed = True
            if not self._idempotency.claim(NAMESPACE_CHAT_TRIGGER, event.message_id):
                self._idempotency.release(NAMESPACE_ASK_CONTENT, content_key)
                print(
                    f"[sub-llm] skip duplicate trigger message_id={event.message_id[:8]}",
                    file=sys.stderr,
                    flush=True,
                )
                return
            trigger_claimed = True

        published = False
        busy_acquired = False
        try:
            if not self._busy.acquire(blocking=False):
                self._publish_reply(event, BUSY_REPLY, question=filtered_question)
                return

            busy_acquired = True
            channel = event.channel or ""
            stt_count, chat_count, bot_reply_count, context_len, has_stream = (
                self._context_buffer.stats(channel)
            )
            context = self._context_buffer.context_text(channel)
            if is_current_activity_question(filtered_question):
                context = (
                    f"{context}\n\n" if context else ""
                ) + current_activity_context_hint(has_stt=stt_count > 0)
            elif stt_count == 0:
                context = (
                    f"{context}\n\n" if context else ""
                ) + current_activity_context_hint(has_stt=False)
            print(
                f"[sub-llm] context stream={has_stream} stt={stt_count} "
                f"chat={chat_count} bot_replies={bot_reply_count} chars={context_len}",
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
            live_game = resolve_live_game_name(self._context_buffer, channel)
            game_reference = build_game_reference(
                filtered_question,
                game_name=live_game,
                provider=self._game_info,
            )
            if game_reference:
                print(
                    f"game_reference game={live_game} chars={len(game_reference)}",
                    file=sys.stderr,
                    flush=True,
                )
            session_recap = build_session_recap_reference(
                filtered_question,
                channel=channel,
                store=self._stream_store,
            )
            if session_recap.text:
                print(
                    f"session_recap summaries={session_recap.summary_count} "
                    f"raw_stt={session_recap.raw_stt_count} "
                    f"qa_excluded={session_recap.qa_summary_count} "
                    f"chars={len(session_recap.text)}",
                    file=sys.stderr,
                    flush=True,
                )
            author = (event.author_name or event.login or "?").strip()
            print(
                f"!ask triggered author={author} question={filtered_question[:80]!r} "
                f"→ calling LLM ({type(self._llm).__name__})",
                file=sys.stderr,
                flush=True,
            )
            ask_result = self._llm.ask(
                filtered_question,
                context=context,
                knowledge=knowledge,
                game_reference=game_reference,
                session_recap_reference=session_recap.text,
            )
            filtered_reply = self._safety.filter_output(ask_result.reply)
            if filtered_reply is None:
                return
            filtered_reply = plain_text_for_chat(filtered_reply)
            if not filtered_reply:
                return
            filtered_reply = cap_reply_for_chat(
                filtered_reply,
                self._config.reply_max_length,
            )
            filtered_reply = cap_reply_for_twitch(
                filtered_reply,
                TWITCH_CHAT_MAX_CHARS,
            )
            if not filtered_reply:
                return
            self._publish_reply(event, filtered_reply, question=filtered_question)
            published = True
            if self._config.qa_memory_mode == "structured" and should_persist_qa_memory(
                ask_result,
                question=filtered_question,
                published_reply=filtered_reply,
                min_memory_value=self._config.qa_memory_min_value,
            ):
                self._publish_qa_memory_record(
                    event,
                    question=filtered_question,
                    reply=filtered_reply,
                    memory_note=ask_result.memory_note,
                    memory_value=ask_result.memory_value,
                )
        finally:
            if busy_acquired:
                self._busy.release()
            if not published and self._idempotency is not None:
                if content_claimed and content_key is not None:
                    self._idempotency.release(NAMESPACE_ASK_CONTENT, content_key)
                if trigger_claimed:
                    self._idempotency.release(
                        NAMESPACE_CHAT_TRIGGER,
                        event.message_id,
                    )

    def _publish_reply(
        self,
        trigger: ChatMessageEvent,
        content: str,
        *,
        question: str = "",
    ) -> None:
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
        reply_to = (trigger.author_name or trigger.login or "").strip()
        self._context_buffer.add_bot_reply(
            trigger.channel or "",
            content,
            question=question,
            reply_to_author=reply_to,
        )

    def _publish_qa_memory_record(
        self,
        trigger: ChatMessageEvent,
        *,
        question: str,
        reply: str,
        memory_note: str,
        memory_value: int,
    ) -> None:
        ask_author = (trigger.author_name or trigger.login or "").strip()
        record = MemoryQaRecordEvent.build(
            channel=trigger.channel or "",
            platform=trigger.platform,
            correlation_id=trigger.message_id,
            question=question,
            reply=reply,
            memory_note=memory_note,
            memory_value=memory_value,
            store_worthy=True,
            ask_author=ask_author,
        )
        self._publish(TOPIC_MEMORY_QA_RECORD, record.to_dict())
        print(
            f"[sub-llm] published {TOPIC_MEMORY_QA_RECORD} "
            f"correlation={trigger.message_id[:8]} memory_value={memory_value}",
            file=sys.stderr,
            flush=True,
        )
