from __future__ import annotations

import threading
import time
from collections import deque

from pkg_tts.protocol import TtsEngine


class TtsPlaybackQueue:
    """序列化 TTS 播放，佇列滿時丟棄最舊項目，並在每次播放後節流。"""

    def __init__(
        self,
        engine: TtsEngine,
        *,
        cooldown_seconds: float = 1.0,
        max_queue_size: int = 20,
    ) -> None:
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be >= 0")
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be >= 1")

        self._engine = engine
        self._cooldown_seconds = cooldown_seconds
        self._max_queue_size = max_queue_size
        self._items: deque[str] = deque()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run, name="tts-playback", daemon=True)
        self._worker.start()

    def enqueue(self, text: str) -> bool:
        """加入佇列；若已滿則丟棄最舊項目。回傳 False 表示此文字取代了一則舊訊息。"""
        if self._stop.is_set():
            return False

        dropped = False
        with self._not_empty:
            if len(self._items) >= self._max_queue_size:
                self._items.popleft()
                dropped = True
            self._items.append(text)
            self._not_empty.notify()

        return not dropped

    def shutdown(self, *, wait: bool = True) -> None:
        self._stop.set()
        with self._not_empty:
            self._not_empty.notify_all()
        if wait:
            self._worker.join()

    def pending_count(self) -> int:
        with self._lock:
            return len(self._items)

    def _run(self) -> None:
        while True:
            with self._not_empty:
                while not self._items and not self._stop.is_set():
                    self._not_empty.wait(timeout=0.5)
                if not self._items:
                    if self._stop.is_set():
                        break
                    continue
                item = self._items.popleft()

            try:
                self._engine.speak(item)
            except Exception:
                pass

            if self._cooldown_seconds > 0 and not self._stop.is_set():
                time.sleep(self._cooldown_seconds)
