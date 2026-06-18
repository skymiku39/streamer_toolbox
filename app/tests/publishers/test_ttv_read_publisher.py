from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable

import pytest

from ingress_ttv_read import publisher as pub


class _FakeReader:
    """模擬 LiveChatReader：start() 阻塞直到 stop() 被呼叫。"""

    created: list[_FakeReader] = []

    def __init__(self, channel: str) -> None:
        self.channel = channel
        self.started = threading.Event()
        self.stop_called = False
        self.close_called = False
        self._release = threading.Event()
        _FakeReader.created.append(self)

    def on_message(self, _callback: Callable[[object], None]) -> None:
        pass

    def start(self) -> None:
        self.started.set()
        self._release.wait(timeout=5)

    def stop(self) -> None:
        self.stop_called = True
        self._release.set()

    def close(self) -> None:
        self.close_called = True


def _wait_until(predicate: Callable[[], bool], timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_current_reader_stop_is_noop_when_empty() -> None:
    current = pub._CurrentReader()
    current.stop()  # 尚未設定 reader 不應拋例外


def test_reader_worker_stops_via_current_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeReader.created.clear()
    monkeypatch.setattr(pub, "LiveChatReader", _FakeReader)

    out_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()
    current = pub._CurrentReader()

    worker = threading.Thread(
        target=pub._reader_worker,
        args=("demo", out_queue, stop_event, current),
        kwargs={"reconnect_delay": 0.01},
        daemon=True,
    )
    worker.start()

    assert _wait_until(lambda: bool(_FakeReader.created) and _FakeReader.created[0].started.is_set())

    # 模擬關閉：設旗標並主動中斷正在阻塞的 reader
    stop_event.set()
    current.stop()

    worker.join(timeout=5)
    assert not worker.is_alive()

    reader = _FakeReader.created[0]
    assert reader.stop_called is True
    assert reader.close_called is True
    assert out_queue.get_nowait() is None


def test_reader_worker_reconnects_until_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeReader.created.clear()
    monkeypatch.setattr(pub, "LiveChatReader", _FakeReader)

    out_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()
    current = pub._CurrentReader()

    worker = threading.Thread(
        target=pub._reader_worker,
        args=("demo", out_queue, stop_event, current),
        kwargs={"reconnect_delay": 0.01},
        daemon=True,
    )
    worker.start()

    # 第一個 reader 啟動後讓它自然結束（reconnect），預期會建立第二個 reader
    assert _wait_until(lambda: bool(_FakeReader.created))
    _FakeReader.created[0].stop()  # 解除第一個 start() 阻塞，觸發重連
    assert _wait_until(lambda: len(_FakeReader.created) >= 2)

    stop_event.set()
    current.stop()
    worker.join(timeout=5)
    assert not worker.is_alive()
