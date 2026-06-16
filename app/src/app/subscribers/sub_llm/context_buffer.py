from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from events import ChatMessageEvent, StreamMetadataEvent, SttSegmentEvent

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


@dataclass(frozen=True)
class BufferedBotReply:
    question: str
    text: str
    reply_to_author: str
    timestamp: datetime


class BotReplyContextBuffer:
    """保存 bot 近期問答對，供 LLM 延續同一對話脈絡（不寫入 RAG）。"""

    def __init__(
        self,
        *,
        window_minutes: int = 30,
        max_pairs: int = 5,
    ) -> None:
        self._window_seconds = max(1, window_minutes) * 60
        self._max_pairs = max(1, max_pairs)
        self._replies_by_channel: dict[str, list[BufferedBotReply]] = {}
        self._lock = threading.Lock()

    def add_reply(
        self,
        channel: str,
        text: str,
        *,
        question: str = "",
        reply_to_author: str = "",
        timestamp: datetime | None = None,
    ) -> None:
        content = text.strip()
        if not content:
            return
        key = normalize_channel(channel)
        reply = BufferedBotReply(
            question=question.strip(),
            text=content,
            reply_to_author=reply_to_author.strip(),
            timestamp=timestamp or datetime.now().astimezone(),
        )
        with self._lock:
            bucket = self._replies_by_channel.setdefault(key, [])
            bucket.append(reply)
            self._prune_locked(key)

    def context_text(self, channel: str) -> str:
        key = normalize_channel(channel)
        with self._lock:
            replies = list(self._replies_by_channel.get(key, []))
        if not replies:
            return ""
        lines = [f"【Bot 近期問答（{key}，最近 {len(replies)} 則）】"]
        for index, reply in enumerate(replies, start=1):
            author = reply.reply_to_author or "觀眾"
            if reply.question:
                lines.append(f"{index}. {author} 問：{reply.question}")
            else:
                lines.append(f"{index}. {author}：（無對應問題）")
            lines.append(f"   bot 答：{reply.text}")
        return "\n".join(lines)

    def count(self, channel: str) -> int:
        key = normalize_channel(channel)
        with self._lock:
            return len(self._replies_by_channel.get(key, []))

    def _prune_locked(self, channel: str) -> None:
        replies = self._replies_by_channel.get(channel)
        if not replies:
            return
        cutoff = replies[-1].timestamp.timestamp() - self._window_seconds
        pruned = [reply for reply in replies if reply.timestamp.timestamp() >= cutoff]
        if len(pruned) > self._max_pairs:
            pruned = pruned[-self._max_pairs :]
        self._replies_by_channel[channel] = pruned


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

    def update(self, event: StreamMetadataEvent) -> bool:
        """更新快照；若 is_live / title / game_name 有變才回傳 True。"""
        channel = normalize_channel(event.channel or "")
        with self._lock:
            previous = self._latest_by_channel.get(channel)
            self._latest_by_channel[channel] = event
        if previous is None:
            return True
        return (
            previous.is_live != event.is_live
            or (previous.title or "") != (event.title or "")
            or (previous.game_name or "") != (event.game_name or "")
        )

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

    def live_game_name(self, channel: str) -> str | None:
        key = normalize_channel(channel)
        with self._lock:
            event = self._latest_by_channel.get(key)
        if event is None or not event.is_live:
            return None
        game_name = (event.game_name or "").strip()
        return game_name or None


class LiveContextBuffer:
    """合併直播 metadata、STT 逐字稿、聊天室與 bot 近期回覆。"""

    def __init__(
        self,
        *,
        window_minutes: int = 5,
        skip_author_ids: frozenset[str] = frozenset(),
        bot_reply_window_minutes: int | None = None,
        bot_reply_max_pairs: int = 5,
    ) -> None:
        self._stt = SttContextBuffer(window_minutes=window_minutes)
        self._chat = ChatContextBuffer(
            window_minutes=window_minutes,
            skip_author_ids=skip_author_ids,
        )
        self._bot_replies = BotReplyContextBuffer(
            window_minutes=bot_reply_window_minutes or max(window_minutes * 3, 15),
            max_pairs=bot_reply_max_pairs,
        )
        self._stream = StreamMetadataBuffer()

    def update_stream_metadata(self, event: StreamMetadataEvent) -> bool:
        return self._stream.update(event)

    def add_segment(self, event: SttSegmentEvent) -> None:
        self._stt.add_segment(event)

    def add_chat_message(self, event: ChatMessageEvent) -> None:
        self._chat.add_message(event)

    def add_bot_reply(
        self,
        channel: str,
        content: str,
        *,
        question: str = "",
        reply_to_author: str = "",
    ) -> None:
        self._bot_replies.add_reply(
            channel,
            content,
            question=question,
            reply_to_author=reply_to_author,
        )

    def context_text(self, channel: str) -> str:
        parts = [
            part
            for part in (
                self._stream.context_text(channel),
                self._stt.context_text(channel),
                self._chat.context_text(channel),
                self._bot_replies.context_text(channel),
            )
            if part
        ]
        return "\n\n".join(parts)

    def stats(self, channel: str) -> tuple[int, int, int, int, bool]:
        stt_count = self._stt.count(channel)
        chat_count = self._chat.count(channel)
        bot_reply_count = self._bot_replies.count(channel)
        has_stream = self._stream.has_metadata(channel)
        return (
            stt_count,
            chat_count,
            bot_reply_count,
            len(self.context_text(channel)),
            has_stream,
        )

    def live_game_name(self, channel: str) -> str | None:
        return self._stream.live_game_name(channel)

    def reconfigure(
        self,
        *,
        window_minutes: int,
        bot_reply_window_minutes: int,
        bot_reply_max_pairs: int,
    ) -> None:
        window_seconds = max(1, window_minutes) * 60
        self._stt._window_seconds = window_seconds
        self._chat._window_seconds = window_seconds
        self._bot_replies._window_seconds = max(1, bot_reply_window_minutes) * 60
        self._bot_replies._max_pairs = max(1, bot_reply_max_pairs)
