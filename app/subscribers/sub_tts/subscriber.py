from __future__ import annotations

import sys
import threading
from typing import Any

from pkg_events import ChatMessageEvent

from sub_tts.filter import MessageFilter
from sub_tts.queue_worker import TtsPlaybackQueue


class ChatTtsSubscriber:
    """處理 chat.message payload，過濾後送入 TTS 佇列。"""

    def __init__(self, message_filter: MessageFilter, playback: TtsPlaybackQueue) -> None:
        self._filter = message_filter
        self._playback = playback
        self._received = 0
        self._spoken = 0
        self._skipped = 0
        self._lock = threading.Lock()

    def handle(self, payload: dict[str, Any]) -> None:
        event = ChatMessageEvent.from_dict(payload)

        with self._lock:
            self._received += 1

        if not self._filter.should_speak(event):
            with self._lock:
                self._skipped += 1
            return

        text = self._filter.format_text(event)
        if self._playback.enqueue(text):
            with self._lock:
                self._spoken += 1

    def stats(self) -> tuple[int, int, int, int]:
        with self._lock:
            return (
                self._received,
                self._spoken,
                self._skipped,
                self._playback.pending_count(),
            )

    def log_stats(self) -> None:
        received, spoken, skipped, pending = self.stats()
        print(
            f"[stats] received={received} spoken={spoken} skipped={skipped} pending={pending}",
            file=sys.stderr,
            flush=True,
        )
