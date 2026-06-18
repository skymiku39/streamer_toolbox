from events import TOPIC_STT_SEGMENT, SttSegmentEvent

from stt_core import build_stt_segment_event
from stt_core import TranscriptSegment


def test_build_stt_segment_event_matches_contract() -> None:
    segment = TranscriptSegment(
        text="辨識出的文字",
        start_sec=120.5,
        end_sec=125.0,
        confidence=0.92,
    )
    event = build_stt_segment_event(
        "Channel_Name",
        segment,
        language="zh",
        segment_id="seg-abc123",
        timestamp="2026-06-12T17:00:00+08:00",
    )

    assert event.channel == "channel_name"
    assert event.platform == "twitch"
    assert event.topic == TOPIC_STT_SEGMENT
    assert event.text == "辨識出的文字"
    assert event.start_sec == 120.5
    assert event.end_sec == 125.0
    assert event.language == "zh"
    assert event.confidence == 0.92

    restored = SttSegmentEvent.from_json(event.to_json())
    assert restored == event
