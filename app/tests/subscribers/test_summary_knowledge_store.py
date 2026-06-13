from __future__ import annotations

from pathlib import Path

from stream_store import ACTIVE_SESSION_KEY, StreamTextStore

from sub_llm.knowledge import SummaryKnowledgeStore


def test_summary_knowledge_store_returns_recent_summaries(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    session_id = "sess-1"
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="聊天摘要 A",
        record_count=2,
    )
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-12T10:05:00+00:00",
        period_end="2026-06-12T10:10:00+00:00",
        source="stt",
        content="語音摘要 B",
        record_count=3,
    )

    knowledge = SummaryKnowledgeStore(store, session_id)
    text = knowledge.query("剛才聊什麼？")

    assert "聊天摘要 A" in text
    assert "語音摘要 B" in text
    assert text.index("聊天摘要 A") < text.index("語音摘要 B")
    store.close()


def test_summary_knowledge_store_resolves_active_session(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    session_id = "active-sess"
    store.set_checkpoint(ACTIVE_SESSION_KEY, session_id)
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="checkpoint 摘要",
        record_count=1,
    )

    knowledge = SummaryKnowledgeStore(store, session_id=None)
    assert "checkpoint 摘要" in knowledge.query("?")

    store.close()
