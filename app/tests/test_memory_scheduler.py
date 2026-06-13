from __future__ import annotations

import threading
import time

from app.workers.memory_trigger import MemoryTriggerHandle
from app.workers.memory_scheduler import wait_for_interval_or_trigger


def test_wait_returns_true_when_trigger_fires() -> None:
    handle = MemoryTriggerHandle()

    def fire() -> None:
        time.sleep(0.05)
        handle.signal()

    threading.Thread(target=fire, daemon=True).start()
    assert wait_for_interval_or_trigger(handle, interval_sec=5.0) is True


def test_wait_returns_false_on_timeout() -> None:
    handle = MemoryTriggerHandle()
    start = time.monotonic()
    assert wait_for_interval_or_trigger(handle, interval_sec=0.05) is False
    assert time.monotonic() - start >= 0.04


def test_trigger_handle_passes_session_id() -> None:
    handle = MemoryTriggerHandle()
    handle.signal(session_id="sess-1")
    assert handle.consume_session_id() == "sess-1"
    assert handle.consume_session_id() is None
