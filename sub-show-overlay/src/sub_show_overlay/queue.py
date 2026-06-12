from __future__ import annotations

import queue
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QueueStats:
    received: int
    enqueued: int
    dropped: int
    coalesced: int


class OverlayMessageQueue:
    """Bounded queue between MQ consumer and overlay render worker."""

    def __init__(self, maxsize: int) -> None:
        self._maxsize = max(1, maxsize)
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=self._maxsize)
        self._lock = threading.Lock()
        self._received = 0
        self._enqueued = 0
        self._dropped = 0
        self._coalesced = 0

    def put(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._received += 1

        try:
            self._queue.put_nowait(payload)
            with self._lock:
                self._enqueued += 1
            return
        except queue.Full:
            pass

        drained: deque[dict[str, Any]] = deque()
        while True:
            try:
                drained.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if drained:
            drained.popleft()
            with self._lock:
                self._dropped += 1

        drained.append(payload)
        for item in drained:
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                with self._lock:
                    self._dropped += 1
                break
        with self._lock:
            self._enqueued += 1

    def get(self, timeout: float | None = 0.5) -> dict[str, Any]:
        return self._queue.get(timeout=timeout)

    def drain_batch(self, *, max_items: int, timeout: float = 0.05) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        try:
            batch.append(self.get(timeout=timeout))
        except queue.Empty:
            return batch

        while len(batch) < max_items:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if len(batch) > 1:
            with self._lock:
                self._coalesced += len(batch) - 1
        return batch

    def stats(self) -> QueueStats:
        with self._lock:
            return QueueStats(
                received=self._received,
                enqueued=self._enqueued,
                dropped=self._dropped,
                coalesced=self._coalesced,
            )
