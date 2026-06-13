from __future__ import annotations

from stream_store.models import TextRecord

from app.workers.memory_timeline import format_chat_timeline, format_stt_timeline


def _chat(record_id: int, ts: str, author: str, text: str) -> TextRecord:
    return TextRecord(
        id=record_id,
        session_id="s",
        source="chat",
        timestamp=ts,
        text=text,
        author=author,
        channel="demo",
        message_id=f"m{record_id}",
    )


def _stt(record_id: int, ts: str, text: str) -> TextRecord:
    return TextRecord(
        id=record_id,
        session_id="s",
        source="stt",
        timestamp=ts,
        text=text,
        author="streamer",
        channel="demo",
        message_id=f"seg{record_id}",
    )


def test_format_chat_timeline_includes_timestamp() -> None:
    timeline = format_chat_timeline([_chat(1, "T1", "alice", "你好")])
    assert timeline == "[T1] alice: 你好"


def test_format_stt_timeline_includes_timestamp() -> None:
    timeline = format_stt_timeline([_stt(1, "T2", "大家好")])
    assert timeline == "[T2] 大家好"
