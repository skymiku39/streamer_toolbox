from __future__ import annotations

from pathlib import Path

from stream_store import ACTIVE_SESSION_KEY, StreamTextStore


def test_list_sessions_returns_counts(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    session_id = "sess-1"
    store.append_chat(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:00:00+00:00",
        text="hi",
        author="A",
        message_id="m1",
    )
    store.append_stt(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:00:30+00:00",
        text="hello",
        segment_id="s1",
    )
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:00:30+00:00",
        source="chat",
        content="chat summary",
        record_count=1,
    )
    sessions = store.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == session_id
    assert sessions[0].chat_count == 1
    assert sessions[0].stt_count == 1
    assert sessions[0].summary_count == 1
    assert sessions[0].unsummarized_count == 2
    store.close()
