from __future__ import annotations

import sys
import threading
from typing import Any

from events import TOPIC_CHAT_MESSAGE, TOPIC_STT_SEGMENT, ChatMessageEvent, SttSegmentEvent

from app.subscribers.stream_record_config import RecordConfig, resolve_session_id
from stream_store import StreamTextStore, set_active_session_for_channel


class StreamRecordWriter:
    """將 chat.message / stt.segment 寫入 StreamTextStore。"""

    def __init__(self, store: StreamTextStore, config: RecordConfig) -> None:
        self._store = store
        self._config = config
        self._session_id: str | None = None
        self._chat_count = 0
        self._stt_count = 0
        self._lock = threading.Lock()

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def handle(self, payload: dict[str, Any]) -> None:
        topic = payload.get("topic", "")
        if topic == TOPIC_CHAT_MESSAGE and self._config.include_chat:
            self._handle_chat(payload)
            return
        if topic == TOPIC_STT_SEGMENT and self._config.include_stt:
            self._handle_stt(payload)

    def _handle_chat(self, payload: dict[str, Any]) -> None:
        event = ChatMessageEvent.from_dict(payload)
        content = event.content.strip()
        if not content:
            return

        channel = event.channel or "unknown"
        with self._lock:
            session_id = resolve_session_id(self._config, channel=channel)
            self._session_id = session_id
            self._store.append_chat(
                session_id=session_id,
                channel=channel,
                timestamp=event.timestamp,
                text=content,
                author=event.author_name,
                message_id=event.message_id,
            )
            set_active_session_for_channel(
                self._store,
                channel=channel,
                session_id=session_id,
            )
            self._chat_count += 1

    def _handle_stt(self, payload: dict[str, Any]) -> None:
        event = SttSegmentEvent.from_dict(payload)
        text = event.text.strip()
        if not text:
            return

        channel = event.channel or "unknown"
        with self._lock:
            session_id = resolve_session_id(self._config, channel=channel)
            self._session_id = session_id
            self._store.append_stt(
                session_id=session_id,
                channel=channel,
                timestamp=event.timestamp,
                text=text,
                segment_id=event.segment_id,
            )
            set_active_session_for_channel(
                self._store,
                channel=channel,
                session_id=session_id,
            )
            self._stt_count += 1

    @property
    def chat_count(self) -> int:
        with self._lock:
            return self._chat_count

    @property
    def stt_count(self) -> int:
        with self._lock:
            return self._stt_count

    def log_stats(self) -> None:
        with self._lock:
            chat_count = self._chat_count
            stt_count = self._stt_count
            session_id = self._session_id
        print(
            f"[stats] session={session_id} chat_records={chat_count} "
            f"stt_records={stt_count} mode={self._config.record_mode} db={self._store.path}",
            file=sys.stderr,
            flush=True,
        )


# 向後相容測試別名
ChatRecordWriter = StreamRecordWriter
