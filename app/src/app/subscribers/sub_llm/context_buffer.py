from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from events import SttSegmentEvent
from stream_store.session import normalize_channel


@dataclass(frozen=True)
class BufferedSegment:
    text: str
    timestamp: datetime
    start_sec: float | None


class SttContextBuffer:
    """依 channel 分區累積 stt.segment，供 LLM 取近期上下文。"""

    def __init__(self, *, window_minutes: int = 5) -> None:
        self._window_seconds = max(1, window_minutes) * 60
        self._segments_by_channel: dict[str, list[BufferedSegment]] = {}
        self._lock = threading.Lock()

    def add_segment(self, event: SttSegmentEvent) -> None:
        channel = normalize_channel(event.channel or "")
        timestamp = datetime.fromisoformat(event.timestamp)
        segment = BufferedSegment(
            text=event.text.strip(),
            timestamp=timestamp,
            start_sec=event.start_sec,
        )
        if not segment.text:
            return
        with self._lock:
            bucket = self._segments_by_channel.setdefault(channel, [])
            bucket.append(segment)
            self._prune_locked(channel)

    def context_text(self, channel: str) -> str:
        key = normalize_channel(channel)
        with self._lock:
            segments = list(self._segments_by_channel.get(key, []))
        if not segments:
            return ""
        lines: list[str] = [f"【直播逐字稿（{key}，最近片段）】"]
        for segment in segments:
            label = f"{segment.start_sec:.0f}s" if segment.start_sec is not None else "?"
            lines.append(f"[{label}] {segment.text}")
        return "\n".join(lines)

    def _prune_locked(self, channel: str) -> None:
        segments = self._segments_by_channel.get(channel)
        if not segments:
            return
        cutoff = segments[-1].timestamp.timestamp() - self._window_seconds
        self._segments_by_channel[channel] = [
            segment for segment in segments if segment.timestamp.timestamp() >= cutoff
        ]
