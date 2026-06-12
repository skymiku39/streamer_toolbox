from __future__ import annotations

from pathlib import Path

from pkg_events import TOPIC_CHAT_MESSAGE, TOPIC_STT_SEGMENT, ChatMessageEvent, SttSegmentEvent
from pkg_stream_store import StreamTextStore

from app.subscribers.stream_record_config import RecordConfig
from app.subscribers.stream_record_writer import StreamRecordWriter


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
    writer = StreamRecordWriter(store, config)
    writer.handle(_payload())
    records = store.fetch_unsummarized_chat("fixed-session")
    assert len(records) == 1
    assert records[0].author == "Viewer"
    assert records[0].text == "測試訊息"
    store.close()


def test_writer_resolves_session_per_channel(tmp_path: Path) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    config = RecordConfig(db_path=str(db_path), session_id=None, record_mode="chat")
    writer = StreamRecordWriter(store, config)
    writer.handle(_payload(channel="caren_surfdemon", message_id="m1"))
    writer.handle(_payload(channel="lupulu0524", message_id="m2", content="第二則"))
    caren = store.fetch_unsummarized_chat("caren_surfdemon_20260612")
    lupulu = store.fetch_unsummarized_chat("lupulu0524_20260612")
    assert len(caren) == 1
    assert len(lupulu) == 1
    store.close()


def _stt_payload(**overrides) -> dict:
    base = SttSegmentEvent(
        schema_version=1,
        topic=TOPIC_STT_SEGMENT,
        platform="twitch",
        channel="demo_channel",
        segment_id="seg-001",
        text="實況主打招呼",
        timestamp="2026-06-12T10:00:00+00:00",
    ).to_dict()
    base.update(overrides)
    return base


def test_writer_persists_stt_segment(tmp_path: Path) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    config = RecordConfig(db_path=str(db_path), session_id="fixed-session", record_mode="stt")
    writer = StreamRecordWriter(store, config)
    writer.handle(_stt_payload())
    records = store.fetch_unsummarized_stt("fixed-session")
    assert len(records) == 1
    assert records[0].text == "實況主打招呼"
    store.close()


def test_writer_both_mode_ignores_wrong_topic(tmp_path: Path) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    config = RecordConfig(db_path=str(db_path), session_id="sess", record_mode="chat")
    writer = StreamRecordWriter(store, config)
    writer.handle(_stt_payload())
    assert not store.fetch_unsummarized_stt("sess")
    store.close()
