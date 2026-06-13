from __future__ import annotations

from pathlib import Path

from stream_store import StreamTextStore, set_active_session_for_channel

from sub_llm.knowledge import SummaryKnowledgeStore


def test_summary_knowledge_store_scoped_by_channel(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    store.save_summary(
        session_id="room_a_20260612",
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="A 房摘要",
        record_count=1,
    )
    store.save_summary(
        session_id="room_b_20260612",
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="B 房摘要",
        record_count=1,
    )
    set_active_session_for_channel(store, channel="room_a", session_id="room_a_20260612")
    set_active_session_for_channel(store, channel="room_b", session_id="room_b_20260612")

    knowledge = SummaryKnowledgeStore(store, session_id=None)
    assert "A 房摘要" in knowledge.query("?", channel="room_a")
    assert "B 房摘要" not in knowledge.query("?", channel="room_a")
    assert "B 房摘要" in knowledge.query("?", channel="room_b")
    store.close()
