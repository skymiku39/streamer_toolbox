from __future__ import annotations

from pathlib import Path

from pkg_stream_store import ACTIVE_SESSION_KEY, StreamTextStore


def test_append_chat_and_fetch_unsummarized(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    store.append_chat(
        session_id="sess-1",
        channel="demo",
        timestamp="2026-06-12T10:00:00+00:00",
        text="hello",
        author="Viewer",
        message_id="m1",
    )
    store.append_chat(
        session_id="sess-1",
        channel="demo",
        timestamp="2026-06-12T10:01:00+00:00",
        text="world",
        author="Viewer2",
        message_id="m2",
    )
    records = store.fetch_unsummarized_chat("sess-1")
    assert len(records) == 2
    assert records[0].text == "hello"
    store.mark_summarized([records[0].id])
    remaining = store.fetch_unsummarized_chat("sess-1")
    assert len(remaining) == 1
    assert remaining[0].text == "world"
    store.close()


def test_save_summary_and_checkpoint(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    store.set_checkpoint(ACTIVE_SESSION_KEY, "sess-1")
    assert store.get_checkpoint(ACTIVE_SESSION_KEY) == "sess-1"
    summary_id = store.save_summary(
        session_id="sess-1",
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="摘要內容",
        record_count=3,
    )
    summaries = store.list_summaries("sess-1")
    assert summary_id == summaries[0].id
    assert summaries[0].content == "摘要內容"
    store.close()
