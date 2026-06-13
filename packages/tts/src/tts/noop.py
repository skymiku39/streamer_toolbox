from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class NoOpTtsEngine:
    """不發聲；可選記錄 spoken 文字供測試驗證。"""

    def __init__(self, *, record: bool = False) -> None:
        self._record = record
        self._spoken: list[str] = []
        self._lock = threading.Lock()

    def speak(self, text: str) -> None:
        if not self._record:
            return
        with self._lock:
            self._spoken.append(text)

    @property
    def spoken(self) -> Sequence[str]:
        with self._lock:
            return tuple(self._spoken)

    def clear(self) -> None:
        with self._lock:
            self._spoken.clear()
