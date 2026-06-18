from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from events import TOPIC_STT_SEGMENT, SttSegmentEvent

from stt_core import TranscriptSegment

__all__ = ["TranscriptSegment", "build_stt_segment_event"]


def build_stt_segment_event(
    channel: str,
    segment: TranscriptSegment,
    *,
    language: str | None = None,
    segment_id: str | None = None,
    timestamp: str | None = None,
) -> SttSegmentEvent:
    return SttSegmentEvent(
        schema_version=1,
        topic=TOPIC_STT_SEGMENT,
        platform="twitch",
        channel=channel.lstrip("#").lower(),
        segment_id=segment_id or str(uuid4()),
        text=segment.text,
        start_sec=segment.start_sec,
        end_sec=segment.end_sec,
        language=language,
        confidence=segment.confidence,
        highlight_score=0.0,
        timestamp=timestamp or datetime.now(UTC).isoformat(),
    )
