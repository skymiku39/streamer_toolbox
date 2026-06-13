from __future__ import annotations

from pathlib import Path

from stream_store import StreamTextStore

from app.memory_view.repair import repair_session_channel_isolation


def test_repair_session_channel_isolation(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    session_id = "skymiku39_20260613"
    store.append_chat(
        session_id=session_id,
        channel="skymiku39",
        timestamp="2026-06-12T17:33:22+00:00",
        text="keep summarized",
        author="u1",
        message_id="m-keep",
    )
    keep_id = store.append_chat(
        session_id=session_id,
        channel="skymiku39",
        timestamp="2026-06-12T17:38:36+00:00",
        text="reset me",
        author="u2",
        message_id="m-reset",
    )
    wrong_id = store.append_chat(
        session_id=session_id,
        channel="test_channel_beta",
        timestamp="2026-06-12T17:38:40+00:00",
        text="wrong room",
        author="u3",
        message_id="m-wrong",
    )
    store.mark_summarized([1, keep_id, wrong_id])
    bad_summary = store.save_summary(
        session_id=session_id,
        period_start="2026-06-12T17:38:36+00:00",
        period_end="2026-06-12T17:38:40+00:00",
        source="chat",
        content="mixed",
        record_count=2,
    )

    report = repair_session_channel_isolation(
        store,
        session_id,
        channel="skymiku39",
        preserve_summarized_chat_ids=[1],
    )

    assert wrong_id in report.migrated_record_ids
    assert bad_summary.id in report.deleted_summary_ids
    assert keep_id in report.reset_chat_record_ids
    assert store.fetch_unsummarized_chat(session_id, channel="skymiku39")
    assert not store.fetch_unsummarized_chat(session_id, channel="test_channel_beta")
    assert store.fetch_unsummarized_chat("test_channel_beta_20260612", channel="test_channel_beta")
    assert not any(summary.id == bad_summary.id for summary in store.list_summaries(session_id))
    store.close()
