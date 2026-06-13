from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from events import ChatMessageEvent, SttSegmentEvent, StreamMetadataEvent
from stream_store.session import normalize_channel


@dataclass(frozen=True)
class BufferedSegment:
    text: str
    timestamp: datetime
    start_sec: float | None


@dataclass(frozen=True)
class BufferedChatLine:
    author: str
    text: str
    timestamp: datetime


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

    def count(self, channel: str) -> int:
        key = normalize_channel(channel)
        with self._lock:
            return len(self._segments_by_channel.get(key, []))

    def _prune_locked(self, channel: str) -> None:
        segments = self._segments_by_channel.get(channel)
        if not segments:
            return
        cutoff = segments[-1].timestamp.timestamp() - self._window_seconds
        self._segments_by_channel[channel] = [
            segment for segment in segments if segment.timestamp.timestamp() >= cutoff
        ]


class ChatContextBuffer:
    """依 channel 分區累積近期聊天室訊息（不含 bot 自身發話）。"""

    def __init__(
        self,
        *,
        window_minutes: int = 5,
        skip_author_ids: frozenset[str] = frozenset(),
        max_lines: int = 80,
    ) -> None:
        self._window_seconds = max(1, window_minutes) * 60
        self._skip_author_ids = skip_author_ids
        self._max_lines = max(1, max_lines)
        self._lines_by_channel: dict[str, list[BufferedChatLine]] = {}
        self._lock = threading.Lock()

    def add_message(self, event: ChatMessageEvent) -> None:
        author_id = (event.author_id or "").strip()
        if author_id and author_id in self._skip_author_ids:
            return
        text = event.content.strip()
        if not text:
            return
        channel = normalize_channel(event.channel or "")
        author = (event.author_name or event.login or "viewer").strip()
        line = BufferedChatLine(
            author=author,
            text=text,
            timestamp=datetime.fromisoformat(event.timestamp),
        )
        with self._lock:
            bucket = self._lines_by_channel.setdefault(channel, [])
            bucket.append(line)
            self._prune_locked(channel)

    def context_text(self, channel: str) -> str:
        key = normalize_channel(channel)
        with self._lock:
            lines = list(self._lines_by_channel.get(key, []))
        if not lines:
            return ""
        rendered = [f"【近期聊天室（{key}）】"]
        for line in lines:
            rendered.append(f"{line.author}: {line.text}")
        return "\n".join(rendered)

    def count(self, channel: str) -> int:
        key = normalize_channel(channel)
        with self._lock:
            return len(self._lines_by_channel.get(key, []))

    def _prune_locked(self, channel: str) -> None:
        lines = self._lines_by_channel.get(channel)
        if not lines:
            return
        cutoff = lines[-1].timestamp.timestamp() - self._window_seconds
        pruned = [line for line in lines if line.timestamp.timestamp() >= cutoff]
        if len(pruned) > self._max_lines:
            pruned = pruned[-self._max_lines :]
        self._lines_by_channel[channel] = pruned


def format_duration_seconds(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class StreamMetadataBuffer:
    """保存各 channel 最新直播 metadata 快照。"""

    def __init__(self) -> None:
        self._latest_by_channel: dict[str, StreamMetadataEvent] = {}
        self._lock = threading.Lock()

    def update(self, event: StreamMetadataEvent) -> None:
        channel = normalize_channel(event.channel or "")
        with self._lock:
            self._latest_by_channel[channel] = event

    def has_metadata(self, channel: str) -> bool:
        key = normalize_channel(channel)
        with self._lock:
            return key in self._latest_by_channel

    def context_text(self, channel: str) -> str:
        key = normalize_channel(channel)
        with self._lock:
            event = self._latest_by_channel.get(key)
        if event is None:
            return ""
        lines = [f"【直播狀態（{key}）】"]
        status = "直播中" if event.is_live else "離線"
        lines.append(f"狀態：{status}")
        if event.display_name:
            lines.append(f"顯示名稱：{event.display_name}")
        if event.title:
            lines.append(f"標題：{event.title}")
        if event.game_name:
            lines.append(f"分類／遊戲：{event.game_name}")
        if event.is_live and event.duration_seconds is not None:
            lines.append(f"已直播：{format_duration_seconds(event.duration_seconds)}")
        if event.viewer_count is not None and event.is_live:
            lines.append(f"觀眾：{event.viewer_count}")
        return "\n".join(lines)


class LiveContextBuffer:
    """合併直播 metadata、STT 逐字稿與聊天室短期記憶。"""

    def __init__(
        self,
        *,
        window_minutes: int = 5,
        skip_author_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._stt = SttContextBuffer(window_minutes=window_minutes)
        self._chat = ChatContextBuffer(
            window_minutes=window_minutes,
            skip_author_ids=skip_author_ids,
        )
        self._stream = StreamMetadataBuffer()

    def update_stream_metadata(self, event: StreamMetadataEvent) -> None:
        self._stream.update(event)

    def add_segment(self, event: SttSegmentEvent) -> None:
        self._stt.add_segment(event)

    def add_chat_message(self, event: ChatMessageEvent) -> None:
        self._chat.add_message(event)

    def context_text(self, channel: str) -> str:
        parts = [
            part
            for part in (
                self._stream.context_text(channel),
                self._stt.context_text(channel),
                self._chat.context_text(channel),
            )
            if part
        ]
        return "\n\n".join(parts)

    def stats(self, channel: str) -> tuple[int, int, int, bool]:
        stt_count = self._stt.count(channel)
        chat_count = self._chat.count(channel)
        has_stream = self._stream.has_metadata(channel)
        return stt_count, chat_count, len(self.context_text(channel)), has_stream
