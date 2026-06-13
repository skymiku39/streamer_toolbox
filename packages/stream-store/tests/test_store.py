from __future__ import annotations

from pathlib import Path

from stream_store import StreamTextStore, set_active_session_for_channel


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
    set_active_session_for_channel(store, channel="demo", session_id="sess-1")
    assert store.get_checkpoint("active_session_id:demo") == "sess-1"
    summary = store.save_summary(
        session_id="sess-1",
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="摘要內容",
        record_count=3,
    )
    summaries = store.list_summaries("sess-1")
    assert summary.id == summaries[0].id
    assert summaries[0].content == "摘要內容"
    store.close()


def test_append_stt_and_fetch_unsummarized(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    store.append_stt(
        session_id="sess-1",
        channel="demo",
        timestamp="2026-06-12T10:00:00+00:00",
        text="大家好",
        segment_id="seg-1",
    )
    records = store.fetch_unsummarized_stt("sess-1")
    assert len(records) == 1
    assert records[0].source == "stt"
    assert records[0].author == "streamer"
    assert records[0].text == "大家好"
    store.close()


def test_fetch_unsummarized_merged_orders_by_timestamp(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    session_id = "sess-1"
    store.append_stt(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:01:00+00:00",
        text="回答",
        segment_id="s1",
    )
    store.append_chat(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:00:00+00:00",
        text="問題",
        author="viewer",
        message_id="m1",
    )
    merged = store.fetch_unsummarized_merged(session_id, sources=["chat", "stt"])
    assert [record.source for record in merged] == ["chat", "stt"]
    store.close()


def test_fetch_unsummarized_filters_by_channel(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    session_id = "mixed_20260613"
    store.append_chat(
        session_id=session_id,
        channel="room_a",
        timestamp="2026-06-12T10:00:00+00:00",
        text="A only",
        author="a",
        message_id="m1",
    )
    store.append_chat(
        session_id=session_id,
        channel="room_b",
        timestamp="2026-06-12T10:01:00+00:00",
        text="B only",
        author="b",
        message_id="m2",
    )
    room_a = store.fetch_unsummarized_chat(session_id, channel="room_a")
    assert len(room_a) == 1
    assert room_a[0].text == "A only"
    room_b = store.fetch_unsummarized_chat(session_id, channel="room_b")
    assert len(room_b) == 1
    assert room_b[0].text == "B only"
    store.close()


def test_delete_summary_and_unmark_summarized(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    session_id = "sess-1"
    record_id = store.append_chat(
        session_id=session_id,
        channel="room",
        timestamp="2026-06-12T10:00:00+00:00",
        text="hello",
        author="u",
        message_id="m1",
    )
    store.mark_summarized([record_id])
    summary = store.save_summary(
        session_id=session_id,
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:00:00+00:00",
        source="chat",
        content="summary",
        record_count=1,
    )
    assert store.delete_summary(summary.id)
    store.unmark_summarized([record_id])
    assert store.fetch_unsummarized_chat(session_id)
    store.close()


def test_relocate_records(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    wrong_session = "room_a_20260612"
    record_id = store.append_chat(
        session_id=wrong_session,
        channel="room_b",
        timestamp="2026-06-12T10:00:00+00:00",
        text="misplaced",
        author="u",
        message_id="m1",
    )
    target = "room_b_20260612"
    store.ensure_session(target, channel="room_b")
    assert store.relocate_records([record_id], target_session_id=target) == 1
    assert not store.fetch_unsummarized_chat(wrong_session, channel="room_b")
    relocated = store.fetch_unsummarized_chat(target, channel="room_b")
    assert len(relocated) == 1
    assert relocated[0].text == "misplaced"
    store.close()
