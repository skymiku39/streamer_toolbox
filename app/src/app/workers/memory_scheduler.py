from __future__ import annotations

import time

from app.workers.memory_trigger import MemoryTriggerHandle
from app.workers.memory_worker import MemoryWorker


def wait_for_interval_or_trigger(handle: MemoryTriggerHandle, interval_sec: float) -> bool:
    """等待定時週期或觸發事件。回傳 True 表示因觸發而提前醒來。"""
    deadline = time.monotonic() + interval_sec
    while True:
        remaining = max(0.0, deadline - time.monotonic())
        if remaining == 0:
            return False
        if handle.wait(timeout=remaining):
            return True


def run_scheduled_worker(
    worker: MemoryWorker,
    handle: MemoryTriggerHandle,
    *,
    interval_sec: float,
) -> None:
    worker.run_once()
    while True:
        wait_for_interval_or_trigger(handle, interval_sec)
        session_id = handle.consume_session_id()
        deep = handle.consume_deep()
        worker.run_once(session_id=session_id, deep=deep)
