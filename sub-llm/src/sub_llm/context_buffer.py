from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from pkg_events import SttSegmentEvent


@dataclass(frozen=True)
class BufferedSegment:
    text: str
    timestamp: datetime
    start_sec: float | None


class SttContextBuffer:
    """累積 stt.segment 文字，依時間窗提供 LLM 上下文。"""

    def __init__(self, *, window_minutes: int = 5) -> None:
        self._window_seconds = max(1, window_minutes) * 60
        self._segments: list[BufferedSegment] = []
        self._lock = threading.Lock()

    def add_segment(self, event: SttSegmentEvent) -> None:
        timestamp = datetime.fromisoformat(event.timestamp)
        segment = BufferedSegment(
            text=event.text.strip(),
            timestamp=timestamp,
            start_sec=event.start_sec,
        )
        if not segment.text:
            return
        with self._lock:
            self._segments.append(segment)
            self._prune_locked()

    def context_text(self) -> str:
        with self._lock:
            if not self._segments:
                return ""
            lines: list[str] = ["【直播逐字稿（最近片段）】"]
            for segment in self._segments:
                label = f"{segment.start_sec:.0f}s" if segment.start_sec is not None else "?"
                lines.append(f"[{label}] {segment.text}")
            return "\n".join(lines)

    def _prune_locked(self) -> None:
        if not self._segments:
            return
        cutoff = self._segments[-1].timestamp.timestamp() - self._window_seconds
        self._segments = [
            segment for segment in self._segments if segment.timestamp.timestamp() >= cutoff
        ]
