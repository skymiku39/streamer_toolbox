from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from events import (
    SOURCE_LOGIC_LLM,
    TOPIC_CHAT_MESSAGE,
    TOPIC_CHAT_REPLY,
    TOPIC_CONFIG_CHANGED,
    TOPIC_MEMORY_QA_RECORD,
    TOPIC_MEMORY_SUMMARY_READY,
    TOPIC_STREAM_METADATA,
    TOPIC_STT_SEGMENT,
    ChatMessageEvent,
    ChatReplyEvent,
    ConfigChangedEvent,
    MemoryQaRecordEvent,
    MemorySummaryReadyEvent,
    StreamMetadataEvent,
    SttSegmentEvent,
)

from control import MODULE_LLM_BOT, active_profile_id
from game_info import GameInfoProvider
from safety import SafetyFilter
from safety.stt_input import is_hallucination_text
from stream_store import StreamTextStore
from stream_store.idempotency import IdempotencyStore
from sub_llm.ask_flow_guard import AskFlowGuard
from sub_llm.chat_format import cap_reply_for_chat, cap_reply_for_twitch, plain_text_for_chat
from sub_llm.config import TWITCH_CHAT_MAX_CHARS, LlmSubscriberConfig
from sub_llm.context_buffer import LiveContextBuffer
from sub_llm.game_context import build_game_reference, resolve_live_game_name
from sub_llm.knowledge import KnowledgeStore
from sub_llm.live_activity import current_activity_context_hint, is_current_activity_question
from sub_llm.prompt_format import INTRA_SEP, join_lines
from sub_llm.llm import LlmClient
from sub_llm.observability import log_event
from sub_llm.qa_memory_gate import should_persist_qa_memory
from sub_llm.resilience import CircuitBreaker, LlmApiError
from sub_llm.session_recap import build_session_recap_reference
from sub_llm.short_term_rag import ShortTermRagStore
from sub_llm.triggers import TriggerMatcher

BUSY_REPLY = "⏳ 上一個問題還在處理中，請稍後再試。"
DEGRADED_REPLY = "⚠️ AI 暫時無法回應，請稍後再試。"
NAMESPACE_CHAT_TRIGGER = "sub_llm.chat.trigger"


def _resolve_stt_min_confidence() -> float:
    raw = os.environ.get("STT_MIN_CONFIDENCE", "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.0


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
        circuit_breaker: CircuitBreaker | None = None,
        flow_guard: AskFlowGuard | None = None,
        short_term_rag: ShortTermRagStore | None = None,
        stt_min_confidence: float | None = None,
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
        self._circuit = circuit_breaker or CircuitBreaker.from_env()
        self._flow_guard = flow_guard
        self._short_term_rag = short_term_rag
        self._stt_min_confidence = (
            stt_min_confidence
            if stt_min_confidence is not None
            else _resolve_stt_min_confidence()
        )
        self._triggers = TriggerMatcher(tuple(config.trigger_prefixes))
        self._busy = threading.Lock()

    def handle(self, payload: dict[str, Any]) -> None:
        topic = payload.get("topic")
        if topic == TOPIC_CONFIG_CHANGED:
            self._handle_config_changed(payload)
            return
        if topic == TOPIC_MEMORY_SUMMARY_READY:
            self._handle_memory_summary_ready(payload)
            return
        if topic == TOPIC_STT_SEGMENT:
            self._handle_stt_segment(payload)
        elif topic == TOPIC_STREAM_METADATA:
            self._handle_stream_metadata(payload)
        elif topic == TOPIC_CHAT_MESSAGE:
            self._handle_chat_message(payload)

    def _handle_memory_summary_ready(self, payload: dict[str, Any]) -> None:
        """摘要就緒時主動索引到 Chroma，讓 !ask 查詢路徑不必負擔同步延遲。"""
        sync = getattr(self._knowledge, "sync", None)
        if not callable(sync):
            return
        try:
            event = MemorySummaryReadyEvent.from_dict(payload)
        except (KeyError, ValueError) as exc:
            print(
                f"[sub-llm] skip invalid memory.summary.ready: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return
        try:
            sync(event.session_id)
        except Exception as exc:  # noqa: BLE001 - 索引失敗不應中斷訂閱
            print(
                f"[sub-llm] memory index failed session={event.session_id}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return
        print(
            f"[sub-llm] memory indexed session={event.session_id} "
            f"source={event.source} summary_id={event.summary_id}",
            file=sys.stderr,
            flush=True,
        )

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
        if is_hallucination_text(event.text, language=event.language):
            return
        if self._stt_min_confidence > 0 and (event.confidence or 0.0) < self._stt_min_confidence:
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

        channel = event.channel or ""

        trigger_claimed = False
        if self._idempotency is not None:
            if not self._idempotency.claim(NAMESPACE_CHAT_TRIGGER, event.message_id):
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
            if self._flow_guard is not None:
                decision = self._flow_guard.check(channel, filtered_question)
                if not decision.should_call_llm:
                    log_event(
                        "ask_decision",
                        action=decision.action,
                        message_id=event.message_id[:8],
                        channel=channel,
                        llm_called=False,
                    )
                    self._publish_reply(
                        event,
                        decision.reply,
                        question=filtered_question,
                        remember=False,
                    )
                    published = True
                    return

            if not self._busy.acquire(blocking=False):
                self._publish_reply(
                    event, BUSY_REPLY, question=filtered_question, remember=False
                )
                return

            busy_acquired = True
            stt_count, chat_count, bot_reply_count, context_len, has_stream = (
                self._context_buffer.stats(channel)
            )
            context = self._context_buffer.context_text(channel)
            if is_current_activity_question(filtered_question):
                context = join_lines(
                    context,
                    current_activity_context_hint(has_stt=stt_count > 0),
                )
            elif stt_count == 0:
                context = join_lines(
                    context,
                    current_activity_context_hint(has_stt=False),
                )
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
            short_term_hit = False
            if self._short_term_rag is not None:
                short_term = self._short_term_rag.query(
                    channel,
                    filtered_question,
                    exclude_questions=self._context_buffer.recent_bot_questions(channel),
                )
                if short_term:
                    short_term_hit = True
                    knowledge = f"{short_term}\n{knowledge}" if knowledge else short_term
                    print(
                        f"[sub-llm] short-term RAG hit chars={len(short_term)}",
                        file=sys.stderr,
                        flush=True,
                    )
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
            if not self._circuit.allow():
                log_event(
                    "ask_decision",
                    action="circuit_open",
                    message_id=event.message_id[:8],
                    channel=channel,
                    llm_called=False,
                )
                self._publish_reply(
                    event, DEGRADED_REPLY, question=filtered_question, remember=False
                )
                published = True
                return
            print(
                f"!ask triggered author={author} question={filtered_question[:80]!r} "
                f"→ calling LLM ({type(self._llm).__name__})",
                file=sys.stderr,
                flush=True,
            )
            started_at = time.monotonic()
            try:
                ask_result = self._llm.ask(
                    filtered_question,
                    context=context,
                    knowledge=knowledge,
                    game_reference=game_reference,
                    session_recap_reference=session_recap.text,
                )
            except LlmApiError as exc:
                self._circuit.record_failure()
                log_event(
                    "ask_decision",
                    action="degraded",
                    message_id=event.message_id[:8],
                    channel=channel,
                    llm_called=True,
                    status=exc.status_code,
                    latency_ms=int((time.monotonic() - started_at) * 1000),
                    error=str(exc)[:120],
                )
                self._publish_reply(
                    event, DEGRADED_REPLY, question=filtered_question, remember=False
                )
                published = True
                return
            latency_ms = int((time.monotonic() - started_at) * 1000)
            self._circuit.record_success()
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
            log_event(
                "ask_decision",
                action="llm",
                message_id=event.message_id[:8],
                channel=channel,
                llm_called=True,
                backend=type(self._llm).__name__,
                latency_ms=latency_ms,
                reply_len=len(filtered_reply),
                knowledge_hit=bool(knowledge),
                short_term_hit=short_term_hit,
                game_ref=bool(game_reference),
                session_recap=bool(session_recap.text),
            )
            if self._flow_guard is not None:
                self._flow_guard.record_reply(channel, filtered_question, filtered_reply)
            if self._short_term_rag is not None:
                self._short_term_rag.index(channel, filtered_question, filtered_reply)
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
                    category=ask_result.category,
                )
        finally:
            if busy_acquired:
                self._busy.release()
            if not published and self._idempotency is not None and trigger_claimed:
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
        remember: bool = True,
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
        # 罐頭／降級回覆不寫入近期問答 buffer，避免污染後續 LLM 上下文。
        if not remember:
            return
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
        category: str = "",
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
            category=category,
        )
        self._publish(TOPIC_MEMORY_QA_RECORD, record.to_dict())
        print(
            f"[sub-llm] published {TOPIC_MEMORY_QA_RECORD} "
            f"correlation={trigger.message_id[:8]} memory_value={memory_value} "
            f"category={category or 'discussion'}",
            file=sys.stderr,
            flush=True,
        )

    def reload_config(self, config: LlmSubscriberConfig, *, safety: SafetyFilter) -> None:
        with self._busy:
            self._config = config
            self._triggers = TriggerMatcher(tuple(config.trigger_prefixes))
            self._safety = safety
            self._context_buffer.reconfigure(
                window_minutes=config.context_window_minutes,
                bot_reply_window_minutes=config.bot_reply_window_minutes,
                bot_reply_max_pairs=config.bot_reply_max_pairs,
            )

    def _handle_config_changed(self, payload: dict[str, Any]) -> None:
        try:
            event = ConfigChangedEvent.from_dict(payload)
        except (KeyError, TypeError, ValueError):
            return
        if event.module_id != MODULE_LLM_BOT:
            return
        if event.profile_id != active_profile_id():
            return
        if event.config_file != "llm_subscriber.json":
            return
        reload = getattr(self, "_config_reload", None)
        if not callable(reload):
            return
        reload()
