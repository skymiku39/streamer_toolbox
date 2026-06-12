from __future__ import annotations

from pkg_stream_store.models import TextRecord

from app.workers.memory_timeline import format_merged_timeline, pair_qa_candidates


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


def test_format_merged_timeline_labels_sources() -> None:
    timeline = format_merged_timeline(
        [
            _chat(1, "T1", "alice", "你好"),
            _stt(2, "T2", "大家好"),
        ]
    )
    assert "[CHAT] alice: 你好" in timeline
    assert "[STT] 大家好" in timeline


def test_pair_qa_candidates_links_chat_to_next_stt() -> None:
    records = [
        _chat(1, "T1", "bob", "幾點下播？"),
        _stt(2, "T2", "大概十點"),
        _chat(3, "T3", "carol", "收到"),
    ]
    pairs = pair_qa_candidates(records)
    assert len(pairs) == 2
    assert pairs[0][0].author == "bob"
    assert pairs[0][1] is not None
    assert pairs[0][1].text == "大概十點"
    assert pairs[1][0].author == "carol"
    assert pairs[1][1] is None
