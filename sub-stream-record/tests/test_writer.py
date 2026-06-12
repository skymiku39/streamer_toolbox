from __future__ import annotations

from pathlib import Path

from pkg_events import TOPIC_CHAT_MESSAGE, ChatMessageEvent
from pkg_stream_store import StreamTextStore

from sub_stream_record.config import RecordConfig
from sub_stream_record.writer import ChatRecordWriter


def _payload(**overrides) -> dict:
    base = ChatMessageEvent(
        schema_version=1,
        topic=TOPIC_CHAT_MESSAGE,
        platform="twitch",
        message_id="msg-001",
        author_name="Viewer",
        content="測試訊息",
        timestamp="2026-06-12T10:00:00+00:00",
        channel="demo_channel",
    ).to_dict()
    base.update(overrides)
    return base


def test_writer_persists_chat_message(tmp_path: Path) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    config = RecordConfig(db_path=str(db_path), session_id="fixed-session", record_mode="chat")
    writer = ChatRecordWriter(store, config)
    writer.handle(_payload())
    records = store.fetch_unsummarized_chat("fixed-session")
    assert len(records) == 1
    assert records[0].author == "Viewer"
    assert records[0].text == "測試訊息"
    store.close()
