from __future__ import annotations

from pathlib import Path

from app.workers.memory_config import MemoryWorkerConfig
from app.workers.memory_summarizer import SummaryDraft, TemplateSummarizer
from app.workers.memory_worker import MemoryWorker
from stream_store import StreamTextStore, set_active_session_for_channel
from stream_store.models import TextRecord


class _SpySummarizer:
    """記錄各摘要方法呼叫次數，驗證 both 模式是否走合併單次呼叫。"""

    def __init__(self) -> None:
        self.chat_calls = 0
        self.stt_calls = 0
        self.both_calls = 0

    def summarize_chat(self, records: list[TextRecord]) -> SummaryDraft:
        self.chat_calls += 1
        return SummaryDraft(content="chat-summary", category="discussion")

    def summarize_stt(self, records: list[TextRecord]) -> SummaryDraft:
        self.stt_calls += 1
        return SummaryDraft(content="stt-summary", category="progress")

    def summarize_both(
        self,
        chat_records: list[TextRecord],
        stt_records: list[TextRecord],
    ) -> tuple[SummaryDraft, SummaryDraft]:
        self.both_calls += 1
        return (
            SummaryDraft(content="chat-summary", category="discussion"),
            SummaryDraft(content="stt-summary", category="progress"),
        )


def test_memory_worker_summarizes_and_marks_records(tmp_path: Path) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    session_id = "sess-demo"
    store.append_chat(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:00:00+00:00",
        text="第一則",
        author="A",
        message_id="m1",
    )
    store.append_chat(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:01:00+00:00",
        text="第二則",
        author="B",
        message_id="m2",
    )
    set_active_session_for_channel(store, channel="demo", session_id=session_id)

    worker = MemoryWorker(
        store,
        MemoryWorkerConfig(
            db_path=str(db_path),
            session_id=None,
            channel="demo",
            interval_minutes=5,
            llm_backend="template",
            batch_limit=200,
            record_mode="chat",
        ),
        TemplateSummarizer(),
    )
    processed = worker.run_once()
    assert processed == 2
    assert not store.fetch_unsummarized_chat(session_id)
    summaries = store.list_summaries(session_id)
    assert len(summaries) == 1
    assert "第一則" in summaries[0].content
    store.close()


def test_memory_worker_summarizes_stt(tmp_path: Path) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    session_id = "sess-stt"
    store.append_stt(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:00:00+00:00",
        text="開場白",
        segment_id="s1",
    )
    set_active_session_for_channel(store, channel="demo", session_id=session_id)

    worker = MemoryWorker(
        store,
        MemoryWorkerConfig(
            db_path=str(db_path),
            session_id=None,
            channel="demo",
            interval_minutes=5,
            llm_backend="template",
            batch_limit=200,
            record_mode="stt",
        ),
        TemplateSummarizer(),
    )
    processed = worker.run_once()
    assert processed == 1
    summaries = store.list_summaries(session_id)
    assert summaries[0].source == "stt"
    assert "開場白" in summaries[0].content
    store.close()


def test_memory_worker_both_separate_aligned_period(tmp_path: Path) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    session_id = "sess-both"
    store.append_chat(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:00:00+00:00",
        text="今天玩什麼？",
        author="viewer1",
        message_id="m1",
    )
    store.append_stt(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:00:30+00:00",
        text="今天打算打 Boss",
        segment_id="s1",
    )
    set_active_session_for_channel(store, channel="demo", session_id=session_id)

    worker = MemoryWorker(
        store,
        MemoryWorkerConfig(
            db_path=str(db_path),
            session_id=None,
            channel="demo",
            interval_minutes=5,
            llm_backend="template",
            batch_limit=200,
            record_mode="both",
        ),
        TemplateSummarizer(),
    )
    processed = worker.run_once()
    assert processed == 2
    assert not store.fetch_unsummarized_chat(session_id)
    assert not store.fetch_unsummarized_stt(session_id)
    summaries = store.list_summaries(session_id, limit=10)
    assert len(summaries) == 2
    by_source = {summary.source: summary for summary in summaries}
    assert "chat" in by_source and "stt" in by_source
    assert by_source["chat"].period_start == by_source["stt"].period_start
    assert by_source["chat"].period_end == by_source["stt"].period_end
    assert "今天玩什麼" in by_source["chat"].content
    assert "Boss" in by_source["stt"].content
    assert "[2026-06-12T10:00:00+00:00]" in by_source["chat"].content
    store.close()


def _seed_both_session(store: StreamTextStore, session_id: str) -> None:
    store.append_chat(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:00:00+00:00",
        text="今天玩什麼？",
        author="viewer1",
        message_id="m1",
    )
    store.append_stt(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:00:30+00:00",
        text="今天打算打 Boss",
        segment_id="s1",
    )
    set_active_session_for_channel(store, channel="demo", session_id=session_id)


def test_memory_worker_both_merge_uses_single_call(tmp_path: Path) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    session_id = "sess-merge"
    _seed_both_session(store, session_id)

    spy = _SpySummarizer()
    worker = MemoryWorker(
        store,
        MemoryWorkerConfig(
            db_path=str(db_path),
            session_id=None,
            channel="demo",
            interval_minutes=5,
            llm_backend="gemini",
            batch_limit=200,
            record_mode="both",
            merge_summary=True,
        ),
        spy,
    )
    processed = worker.run_once()
    assert processed == 2
    assert spy.both_calls == 1
    assert spy.chat_calls == 0
    assert spy.stt_calls == 0
    assert len(store.list_summaries(session_id, limit=10)) == 2
    store.close()


def test_memory_worker_both_merge_disabled_calls_separately(tmp_path: Path) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    session_id = "sess-no-merge"
    _seed_both_session(store, session_id)

    spy = _SpySummarizer()
    worker = MemoryWorker(
        store,
        MemoryWorkerConfig(
            db_path=str(db_path),
            session_id=None,
            channel="demo",
            interval_minutes=5,
            llm_backend="gemini",
            batch_limit=200,
            record_mode="both",
            merge_summary=False,
        ),
        spy,
    )
    processed = worker.run_once()
    assert processed == 2
    assert spy.both_calls == 0
    assert spy.chat_calls == 1
    assert spy.stt_calls == 1
    store.close()


def test_memory_worker_deep_run_uses_deep_summarizer(tmp_path: Path) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    session_id = "sess-deep"
    _seed_both_session(store, session_id)

    normal = _SpySummarizer()
    deep = _SpySummarizer()
    worker = MemoryWorker(
        store,
        MemoryWorkerConfig(
            db_path=str(db_path),
            session_id=None,
            channel="demo",
            interval_minutes=5,
            llm_backend="gemini",
            batch_limit=200,
            record_mode="both",
            merge_summary=True,
        ),
        normal,
        deep_summarizer=deep,
    )
    worker.run_once(deep=True)
    assert deep.both_calls == 1
    assert normal.both_calls == 0
    store.close()
