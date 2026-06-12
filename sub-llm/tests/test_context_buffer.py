from datetime import datetime, timedelta, timezone

from pkg_events import TOPIC_STT_SEGMENT, SttSegmentEvent

from sub_llm.context_buffer import SttContextBuffer


def _segment(text: str, *, offset_minutes: int = 0) -> SttSegmentEvent:
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)).isoformat()
    return SttSegmentEvent(
        schema_version=1,
        topic=TOPIC_STT_SEGMENT,
        platform="twitch",
        channel="demo",
        segment_id=f"seg-{text}",
        text=text,
        timestamp=timestamp,
        start_sec=10.0,
    )


def test_context_text_includes_recent_segments() -> None:
    buffer = SttContextBuffer(window_minutes=5)
    buffer.add_segment(_segment("第一段"))
    buffer.add_segment(_segment("第二段"))
    context = buffer.context_text()
    assert "第一段" in context
    assert "第二段" in context


def test_context_text_prunes_old_segments() -> None:
    buffer = SttContextBuffer(window_minutes=1)
    buffer.add_segment(_segment("舊片段", offset_minutes=10))
    buffer.add_segment(_segment("新片段", offset_minutes=0))
    context = buffer.context_text()
    assert "舊片段" not in context
    assert "新片段" in context
