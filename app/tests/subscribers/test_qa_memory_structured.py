from events import MemoryQaRecordEvent
from stream_store import StreamTextStore

from app.subscribers.stream_record_config import RecordConfig
from sub_qa_memory_structured.writer import StructuredQaMemoryWriter


def test_structured_writer_persists_qa_summary(tmp_path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    config = RecordConfig(db_path=str(tmp_path / "test.db"), session_id=None, record_mode="chat")
    writer = StructuredQaMemoryWriter(store, config)
    payload = MemoryQaRecordEvent.build(
        channel="demo",
        platform="twitch",
        correlation_id="msg-qa-1",
        question="現在在玩什麼",
        reply="DND 第五版",
        memory_note="觀眾問目前在玩什麼，bot 答 DND 第五版。",
        memory_value=4,
        store_worthy=True,
        ask_author="alice",
    ).to_dict()

    summary = writer.handle(payload)
    assert summary is not None
    assert summary.source == "qa"
    assert "DND" in summary.content
    listed = store.list_summaries(summary.session_id, limit=1)
    assert listed[0].id == summary.id
