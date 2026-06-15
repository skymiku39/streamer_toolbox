from events import (
    SOURCE_LOGIC_LLM,
    TOPIC_CHAT_MESSAGE,
    TOPIC_CHAT_REPLY,
    TOPIC_STT_SEGMENT,
    TOPIC_STREAM_METADATA,
    ChatMessageEvent,
    SttSegmentEvent,
)
from safety import PassThroughSafetyFilter

from sub_llm.ask_response import AskResponse
from sub_llm.config import LlmSubscriberConfig
from sub_llm.context_buffer import LiveContextBuffer
from sub_llm.handler import BUSY_REPLY, LlmSubscriber
from sub_llm.knowledge import EmptyKnowledgeStore
from sub_llm.llm import TemplateLlmClient


def _chat_payload(
    content: str,
    *,
    channel: str = "demo_channel",
    message_id: str = "msg-1",
    author_name: str = "viewer",
    author_id: str | None = "viewer-id",
) -> dict:
    return ChatMessageEvent(
        schema_version=1,
        topic=TOPIC_CHAT_MESSAGE,
        platform="twitch",
        message_id=message_id,
        author_name=author_name,
        author_id=author_id,
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
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_chat_payload("!ask 什麼是 SOLID？"))

    assert len(published) == 1
    topic, payload = published[0]
    assert topic == TOPIC_CHAT_REPLY
    assert payload["source"] == SOURCE_LOGIC_LLM
    assert payload["correlation_id"] == "msg-1"
    assert "SOLID" in payload["content"]


def test_bot_author_trigger_is_ignored() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
        skip_trigger_author_ids=frozenset({"bot-id"}),
    )

    subscriber.handle(
        _chat_payload(
            "!ask 這是 BOT 自己的訊息",
            message_id="msg-bot-1",
            author_id="bot-id",
        )
    )

    assert published == []


def test_bot_login_trigger_is_ignored() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
        skip_trigger_logins=frozenset({"mybot"}),
    )

    subscriber.handle(
        _chat_payload(
            "!ask 這是 BOT 自己的訊息",
            message_id="msg-bot-2",
            author_name="MyBot",
            author_id=None,
        )
    )

    assert published == []


def test_stt_segment_accumulates_context_for_reply() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_stt_payload("主播正在講設計原則"))
    subscriber.handle(_chat_payload("!ask 剛剛說什麼？"))

    assert len(published) == 1
    assert "近期直播上下文" in published[0][1]["content"]


def test_chat_messages_accumulate_context_for_reply() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_chat_payload("LNG Live 是實況團體"))
    subscriber.handle(_chat_payload("!ask 誰是 LNG"))

    assert len(published) == 1
    assert "近期直播上下文" in published[0][1]["content"]


def test_stream_metadata_updates_context_for_reply() -> None:
    from events import StreamMetadataEvent

    published: list[tuple[str, dict]] = []
    captured: dict[str, str] = {}

    class CapturingLlm:
        def ask(
            self,
            question: str,
            *,
            context: str,
            knowledge: str = "",
            game_reference: str = "",
            session_recap_reference: str = "",
        ) -> AskResponse:
            captured["context"] = context
            return AskResponse(reply="metadata-aware reply")

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=CapturingLlm(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(
        StreamMetadataEvent(
            schema_version=1,
            topic=TOPIC_STREAM_METADATA,
            platform="twitch",
            channel="demo_channel",
            timestamp="2026-06-13T10:00:00+00:00",
            snapshot_id="meta-1",
            is_live=True,
            title="Just Chatting 測試",
            game_name="Just Chatting",
            duration_seconds=1800,
        ).to_dict()
    )
    subscriber.handle(_chat_payload("!ask 現在在播什麼？"))

    assert len(published) == 1
    assert "Just Chatting 測試" in captured["context"]
    assert "【直播狀態" in captured["context"]


def test_stream_metadata_duration_tick_does_not_spam_stderr(capsys) -> None:
    from events import StreamMetadataEvent

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: None,
    )

    base = StreamMetadataEvent(
        schema_version=1,
        topic=TOPIC_STREAM_METADATA,
        platform="twitch",
        channel="demo_channel",
        timestamp="2026-06-13T10:00:00+00:00",
        snapshot_id="meta-1",
        is_live=True,
        title="Just Chatting 測試",
        game_name="Just Chatting",
        duration_seconds=1800,
    )
    subscriber.handle(base.to_dict())
    subscriber.handle(
        StreamMetadataEvent(
            schema_version=1,
            topic=TOPIC_STREAM_METADATA,
            platform="twitch",
            channel="demo_channel",
            timestamp="2026-06-13T10:01:00+00:00",
            snapshot_id="meta-2",
            is_live=True,
            title="Just Chatting 測試",
            game_name="Just Chatting",
            duration_seconds=1860,
        ).to_dict()
    )

    stderr = capsys.readouterr().err
    assert stderr.count("stream metadata updated") == 1


def test_stt_context_does_not_leak_across_channels() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
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
        context_buffer=LiveContextBuffer(window_minutes=5),
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
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    assert subscriber._busy.acquire(blocking=False)
    subscriber.handle(_chat_payload("!ask 第一題"))
    subscriber.handle(_chat_payload("!ask 第二題"))
    subscriber._busy.release()

    assert len(published) == 2
    assert published[1][1]["content"] == BUSY_REPLY


def test_busy_reply_releases_idempotency_for_retry(tmp_path) -> None:
    from stream_store.idempotency import IdempotencyStore

    published: list[tuple[str, dict]] = []
    llm = _CountingLlmClient()
    store = IdempotencyStore(tmp_path / "dedup.db")

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=llm,
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
        idempotency=store,
    )

    assert subscriber._busy.acquire(blocking=False)
    subscriber.handle(_chat_payload("!ask busy test", message_id="msg-busy-1"))
    assert len(published) == 1
    assert published[0][1]["content"] == BUSY_REPLY

    subscriber._busy.release()
    subscriber.handle(_chat_payload("!ask busy test", message_id="msg-busy-2"))

    assert llm.calls == 1
    assert len(published) == 2
    assert published[1][1]["content"] != BUSY_REPLY
    store.close()


class _MarkdownLlmClient:
    def ask(
        self,
        question: str,
        *,
        context: str,
        knowledge: str = "",
        game_reference: str = "",
        session_recap_reference: str = "",
    ) -> AskResponse:
        return AskResponse(reply="**重點**：這是*測試*回覆")


def test_reply_strips_markdown_for_chat() -> None:
    published: list[tuple[str, dict]] = []
    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=_MarkdownLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_chat_payload("!ask 測試"))

    assert published[0][1]["content"] == "重點：這是測試回覆"


class _LongReplyLlmClient:
    def ask(
        self,
        question: str,
        *,
        context: str,
        knowledge: str = "",
        game_reference: str = "",
        session_recap_reference: str = "",
    ) -> AskResponse:
        return AskResponse(reply="這" * 80 + "。")


def test_reply_is_capped_by_content_length() -> None:
    from sub_llm.chat_format import count_reply_content_chars

    published: list[tuple[str, dict]] = []
    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"], reply_max_length=50),
        llm=_LongReplyLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_chat_payload("!ask 長回覆"))

    content = published[0][1]["content"]
    assert count_reply_content_chars(content) == 50


def test_hallucination_stt_segment_is_ignored() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_stt_payload("thanks for watching"))
    subscriber.handle(_chat_payload("!ask 摘要？"))

    assert "逐字稿" not in published[0][1]["content"]


class _CountingLlmClient:
    def __init__(self) -> None:
        self.calls = 0

    def ask(
        self,
        question: str,
        *,
        context: str,
        knowledge: str = "",
        game_reference: str = "",
        session_recap_reference: str = "",
    ) -> AskResponse:
        self.calls += 1
        return AskResponse(reply=f"answer-{self.calls}")


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
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
        idempotency=store,
    )

    payload = _chat_payload("!ask 重複測試")
    subscriber.handle(payload)
    subscriber.handle(payload)

    assert llm.calls == 1
    assert len(published) == 1
    store.close()


def test_bot_reply_appears_in_follow_up_ask_context() -> None:
    captured: list[str] = []

    class CapturingLlm:
        def ask(
            self,
            question: str,
            *,
            context: str,
            knowledge: str = "",
            game_reference: str = "",
            session_recap_reference: str = "",
        ) -> AskResponse:
            captured.append(context)
            if len(captured) == 1:
                return AskResponse(reply="我們正在玩 DND 第五版")
            return AskResponse(reply="延續上一題")

    published: list[tuple[str, dict]] = []
    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=CapturingLlm(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5, bot_reply_window_minutes=30),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_chat_payload("!ask 我們在玩什麼？", author_name="alice"))
    subscriber.handle(_chat_payload("!ask 剛剛那個遊戲規則版本？", message_id="msg-2"))

    assert len(published) == 2
    assert "【Bot 近期問答" in captured[1]
    assert "我們在玩什麼？" in captured[1]
    assert "DND" in captured[1]
    assert "alice" in captured[1]


def test_high_value_ask_publishes_memory_qa_record() -> None:
    from events import TOPIC_MEMORY_QA_RECORD

    class MemoryLlm:
        def ask(
            self,
            question: str,
            *,
            context: str,
            knowledge: str = "",
            game_reference: str = "",
            session_recap_reference: str = "",
        ) -> AskResponse:
            return AskResponse(
                reply="我們在玩 DND 第五版",
                store_worthy=True,
                memory_value=4,
                memory_note="觀眾問目前在玩什麼，bot 答 DND 第五版。",
            )

    published: list[tuple[str, dict]] = []
    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"], qa_memory_mode="structured"),
        llm=MemoryLlm(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_chat_payload("!ask 現在在玩什麼？", author_name="alice"))

    topics = [topic for topic, _ in published]
    assert TOPIC_CHAT_REPLY in topics
    assert TOPIC_MEMORY_QA_RECORD in topics
    qa_payload = next(payload for topic, payload in published if topic == TOPIC_MEMORY_QA_RECORD)
    assert qa_payload["memory_note"].startswith("觀眾問")


def test_duplicate_ask_content_with_different_message_ids_is_ignored(tmp_path) -> None:
    from stream_store.idempotency import IdempotencyStore

    published: list[tuple[str, dict]] = []
    llm = _CountingLlmClient()
    store = IdempotencyStore(tmp_path / "dedup.db")

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=llm,
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
        idempotency=store,
    )

    subscriber.handle(_chat_payload("!ask 同一題", message_id="msg-a"))
    subscriber.handle(_chat_payload("!ask 同一題", message_id="msg-b"))

    assert llm.calls == 1
    assert len(published) == 1
    store.close()


def test_failed_output_releases_idempotency_for_retry(tmp_path) -> None:
    from safety import SafetyFilter
    from stream_store.idempotency import IdempotencyStore

    class BlockOutputSafety(SafetyFilter):
        def filter_input(self, text: str) -> str | None:
            return text

        def filter_output(self, text: str) -> str | None:
            return None

    published: list[tuple[str, dict]] = []
    llm = _CountingLlmClient()
    store = IdempotencyStore(tmp_path / "dedup.db")

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=llm,
        safety=BlockOutputSafety(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
        idempotency=store,
    )

    payload = _chat_payload("!ask 重試測試")
    subscriber.handle(payload)
    subscriber.handle(payload)

    assert llm.calls == 2
    assert published == []
    store.close()


def test_reload_config_updates_triggers() -> None:
    published: list[tuple[str, dict]] = []

    subscriber = LlmSubscriber(
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        knowledge=EmptyKnowledgeStore(),
        context_buffer=LiveContextBuffer(window_minutes=5),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_chat_payload("!quiz 第一題"))
    assert published == []

    subscriber.reload_config(
        LlmSubscriberConfig(trigger_prefixes=["!quiz"]),
        safety=PassThroughSafetyFilter(),
    )
    subscriber.handle(_chat_payload("!quiz 第一題"))

    assert len(published) == 1
    assert published[0][0] == TOPIC_CHAT_REPLY
