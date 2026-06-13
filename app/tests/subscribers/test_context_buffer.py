from datetime import datetime, timedelta, timezone

from events import TOPIC_STT_SEGMENT, SttSegmentEvent

from sub_llm.context_buffer import SttContextBuffer


def _segment(text: str, *, channel: str, offset_minutes: int = 0) -> SttSegmentEvent:
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)).isoformat()
    return SttSegmentEvent(
        schema_version=1,
        topic=TOPIC_STT_SEGMENT,
        platform="twitch",
        channel=channel,
        segment_id=f"seg-{channel}-{text}",
        text=text,
        timestamp=timestamp,
        start_sec=10.0,
    )


def test_context_text_includes_recent_segments_for_channel() -> None:
    buffer = SttContextBuffer(window_minutes=5)
    buffer.add_segment(_segment("第一段", channel="room_a"))
    buffer.add_segment(_segment("第二段", channel="room_a"))
    context = buffer.context_text("room_a")
    assert "第一段" in context
    assert "第二段" in context


def test_context_text_prunes_old_segments() -> None:
    buffer = SttContextBuffer(window_minutes=1)
    buffer.add_segment(_segment("舊片段", channel="demo", offset_minutes=10))
    buffer.add_segment(_segment("新片段", channel="demo", offset_minutes=0))
    context = buffer.context_text("demo")
    assert "舊片段" not in context
    assert "新片段" in context


def test_context_text_isolated_by_channel() -> None:
    buffer = SttContextBuffer(window_minutes=5)
    buffer.add_segment(_segment("A 房間語音", channel="room_a"))
    buffer.add_segment(_segment("B 房間語音", channel="room_b"))
    context_a = buffer.context_text("room_a")
    context_b = buffer.context_text("room_b")
    assert "A 房間語音" in context_a
    assert "B 房間語音" not in context_a
    assert "B 房間語音" in context_b
    assert "A 房間語音" not in context_b
