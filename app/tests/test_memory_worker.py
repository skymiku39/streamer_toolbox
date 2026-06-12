from __future__ import annotations

from pathlib import Path

from pkg_stream_store import ACTIVE_SESSION_KEY, StreamTextStore

from app.workers.memory_config import MemoryWorkerConfig
from app.workers.memory_summarizer import TemplateSummarizer
from app.workers.memory_worker import MemoryWorker


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
    store.set_checkpoint(ACTIVE_SESSION_KEY, session_id)

    worker = MemoryWorker(
        store,
        MemoryWorkerConfig(
            db_path=str(db_path),
            session_id=None,
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
    store.set_checkpoint(ACTIVE_SESSION_KEY, session_id)

    worker = MemoryWorker(
        store,
        MemoryWorkerConfig(
            db_path=str(db_path),
            session_id=None,
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
