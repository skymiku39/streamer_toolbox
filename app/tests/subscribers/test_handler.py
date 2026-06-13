from events import (
    SOURCE_LOGIC_LLM,
    TOPIC_CHAT_MESSAGE,
    TOPIC_CHAT_REPLY,
    TOPIC_STT_SEGMENT,
    ChatMessageEvent,
    SttSegmentEvent,
)
from safety import PassThroughSafetyFilter

from sub_llm.config import LlmSubscriberConfig
from sub_llm.context_buffer import SttContextBuffer
from sub_llm.handler import BUSY_REPLY, LlmSubscriber
from sub_llm.knowledge import EmptyKnowledgeStore
from sub_llm.llm import TemplateLlmClient


def _chat_payload(content: str, *, channel: str = "demo_channel") -> dict:
    return ChatMessageEvent(
        schema_version=1,
        topic=TOPIC_CHAT_MESSAGE,
        platform="twitch",
        message_id="msg-1",
        author_name="viewer",
        content=content,
        timestamp="2026-06-12T17:00:00+08:00",
        channel=channel,
    ).to_dict()


def _stt_payload(text: str, *, channel: str = "demo_channel") -> dict:
    return SttSegmentEvent(
        schema_version=1,
        topic=TOPIC_STT_SEGMENT,
        platform="twitch",
        channel=channel,
        segment_id="seg-1",
        text=text,
        timestamp="2026-06-12T17:00:00+08:00",
        start_sec=30.0,
    ).to_dict()


def test_chat_trigger_publishes_chat_reply() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=SttContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_chat_payload("!ask 什麼是 SOLID？"))

    assert len(published) == 1
    topic, payload = published[0]
    assert topic == TOPIC_CHAT_REPLY
    assert payload["source"] == SOURCE_LOGIC_LLM
    assert payload["correlation_id"] == "msg-1"
    assert "SOLID" in payload["content"]


def test_stt_segment_accumulates_context_for_reply() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=SttContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_stt_payload("主播正在講設計原則"))
    subscriber.handle(_chat_payload("!ask 剛剛說什麼？"))

    assert len(published) == 1
    assert "逐字稿" in published[0][1]["content"]


def test_stt_context_does_not_leak_across_channels() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=SttContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_stt_payload("B 房秘密", channel="room_b"))
    subscriber.handle(_chat_payload("!ask 剛剛說什麼？", channel="room_a"))

    assert len(published) == 1
    assert "B 房秘密" not in published[0][1]["content"]


def test_non_trigger_chat_is_ignored() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=SttContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_chat_payload("一般聊天"))
    assert published == []


def test_busy_lock_returns_busy_reply() -> None:
    published: list[tuple[str, dict]] = []
    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=SttContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    assert subscriber._busy.acquire(blocking=False)
    subscriber.handle(_chat_payload("!ask 第一題"))
    subscriber.handle(_chat_payload("!ask 第二題"))
    subscriber._busy.release()

    assert len(published) == 2
    assert published[1][1]["content"] == BUSY_REPLY


class _MarkdownLlmClient:
    def ask(self, question: str, *, context: str, knowledge: str = "") -> str:
        return "**重點**：這是*測試*回覆"


def test_reply_strips_markdown_for_chat() -> None:
    published: list[tuple[str, dict]] = []
    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=_MarkdownLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=SttContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_chat_payload("!ask 測試"))

    assert published[0][1]["content"] == "重點：這是測試回覆"


def test_hallucination_stt_segment_is_ignored() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=SttContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_stt_payload("thanks for watching"))
    subscriber.handle(_chat_payload("!ask 摘要？"))

    assert "逐字稿" not in published[0][1]["content"]


class _CountingLlmClient:
    def __init__(self) -> None:
        self.calls = 0

    def ask(self, question: str, *, context: str, knowledge: str = "") -> str:
        self.calls += 1
        return f"answer-{self.calls}"


def test_duplicate_message_id_is_ignored(tmp_path) -> None:
    from stream_store.idempotency import IdempotencyStore

    published: list[tuple[str, dict]] = []
    llm = _CountingLlmClient()
    store = IdempotencyStore(tmp_path / "dedup.db")

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=llm,
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=SttContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
        idempotency=store,
    )

    payload = _chat_payload("!ask 重複測試")
    subscriber.handle(payload)
    subscriber.handle(payload)

    assert llm.calls == 1
    assert len(published) == 1
    store.close()
