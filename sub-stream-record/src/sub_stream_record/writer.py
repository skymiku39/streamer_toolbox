from __future__ import annotations

import sys
import threading
from typing import Any

from pkg_events import ChatMessageEvent
from pkg_stream_store import ACTIVE_SESSION_KEY, StreamTextStore

from sub_stream_record.config import RecordConfig, resolve_session_id


class ChatRecordWriter:
    """將 chat.message 寫入 StreamTextStore。"""

    def __init__(self, store: StreamTextStore, config: RecordConfig) -> None:
        self._store = store
        self._config = config
        self._session_id: str | None = None
        self._count = 0
        self._lock = threading.Lock()

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def handle(self, payload: dict[str, Any]) -> None:
        event = ChatMessageEvent.from_dict(payload)
        content = event.content.strip()
        if not content:
            return

        channel = event.channel or "unknown"
        with self._lock:
            session_id = resolve_session_id(self._config, channel=channel)
            if self._session_id != session_id:
                self._session_id = session_id
            self._store.append_chat(
                session_id=session_id,
                channel=channel,
                timestamp=event.timestamp,
                text=content,
                author=event.author_name,
                message_id=event.message_id,
            )
            self._store.set_checkpoint(ACTIVE_SESSION_KEY, session_id)
            self._count += 1

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    def log_stats(self) -> None:
        with self._lock:
            count = self._count
            session_id = self._session_id
        print(
            f"[stats] session={session_id} chat_records={count} db={self._store.path}",
            file=sys.stderr,
            flush=True,
        )
