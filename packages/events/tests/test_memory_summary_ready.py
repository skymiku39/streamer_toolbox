import json

import pytest

from events import TOPIC_MEMORY_SUMMARY_READY, MemorySummaryReadyEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_MEMORY_SUMMARY_READY,
        "summary_id": 7,
        "session_id": "demo_20260612",
        "source": "chat",
        "period_start": "2026-06-12T10:00:00+00:00",
        "period_end": "2026-06-12T10:30:00+00:00",
        "record_count": 42,
        "created_at": "2026-06-12T10:31:00+00:00",
        "content": "摘要內容",
    }


def test_round_trip_json() -> None:
    event = MemorySummaryReadyEvent.from_dict(_sample_payload())
    restored = MemorySummaryReadyEvent.from_json(event.to_json())
    assert restored == event


def test_build() -> None:
    event = MemorySummaryReadyEvent.build(
        summary_id=1,
        session_id="sess",
        source="stt",
        period_start="a",
        period_end="b",
        record_count=3,
        content="hello",
    )
    assert event.topic == TOPIC_MEMORY_SUMMARY_READY
    assert event.source == "stt"


def test_build_qa_source() -> None:
    event = MemorySummaryReadyEvent.build(
        summary_id=2,
        session_id="sess",
        source="qa",
        period_start="a",
        period_end="b",
        record_count=1,
        content="bot 問答記憶",
    )
    assert event.source == "qa"


@pytest.mark.parametrize("field_name", ["session_id", "content", "created_at"])
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        MemorySummaryReadyEvent.from_dict(payload)
