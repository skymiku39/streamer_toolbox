from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from stream_store.models import Summary

from app.workers.memory_config import MemoryWorkerConfig
from app.workers.memory_summarizer import TemplateSummarizer
from app.workers.memory_worker import MemoryWorker


def test_memory_worker_publishes_summary_ready(tmp_path: Path) -> None:
    from stream_store import StreamTextStore

    store = StreamTextStore(tmp_path / "test.db")
    session_id = "sess-pub"
    store.append_chat(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-12T10:00:00+00:00",
        text="hello",
        author="A",
        message_id="m1",
    )
    publisher = MagicMock()
    worker = MemoryWorker(
        store,
        MemoryWorkerConfig(
            db_path=str(tmp_path / "test.db"),
            session_id=session_id,
            channel="demo",
            interval_minutes=30,
            llm_backend="template",
            batch_limit=200,
            record_mode="chat",
        ),
        TemplateSummarizer(),
        summary_publisher=publisher,
    )
    worker.run_once()
    publisher.publish.assert_called_once()
    summary: Summary = publisher.publish.call_args.args[0]
    assert summary.session_id == session_id
    assert summary.source == "chat"
    assert "hello" in summary.content
    store.close()
