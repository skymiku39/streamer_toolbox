"""聊天訊息節流（同步版，對照 twitch_api MessageThrottle）。"""

from __future__ import annotations

import threading
import time
from collections import deque


class MessageThrottle:
    """
    限流器：
    - 全域 window_seconds 秒最多 window_limit 則
    - 同頻道至少間隔 per_channel_interval_seconds 秒
    """

    def __init__(
        self,
        window_limit: int = 20,
        window_seconds: float = 30.0,
        per_channel_interval_seconds: float = 1.0,
    ) -> None:
        self._window_limit = window_limit
        self._window_seconds = window_seconds
        self._per_channel_interval_seconds = per_channel_interval_seconds
        self._send_lock = threading.Lock()
        self._send_timestamps: deque[float] = deque()
        self._channel_last_sent: dict[str, float] = {}

    def wait(self, channel_name: str) -> None:
        normalized_channel = (channel_name or "").lower()
        while True:
            wait_seconds = 0.0
            with self._send_lock:
                now = time.monotonic()

                while (
                    self._send_timestamps
                    and (now - self._send_timestamps[0]) >= self._window_seconds
                ):
                    self._send_timestamps.popleft()

                if len(self._send_timestamps) >= self._window_limit:
                    oldest = self._send_timestamps[0]
                    wait_seconds = max(wait_seconds, self._window_seconds - (now - oldest))

                last_sent = self._channel_last_sent.get(normalized_channel)
                if last_sent is not None:
                    wait_seconds = max(
                        wait_seconds, self._per_channel_interval_seconds - (now - last_sent)
                    )

                if wait_seconds <= 0:
                    sent_at = time.monotonic()
                    self._send_timestamps.append(sent_at)
                    self._channel_last_sent[normalized_channel] = sent_at
                    return

            time.sleep(wait_seconds)
