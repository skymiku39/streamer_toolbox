from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.processes.process_lock import acquire_process_lock, pid_is_alive


def test_pid_is_alive_current_process() -> None:
    assert pid_is_alive(os.getpid()) is True


def test_pid_is_alive_dead_process() -> None:
    assert pid_is_alive(999999999) is False


def test_acquire_process_lock_rejects_second_holder(tmp_path: Path) -> None:
    lock_dir = tmp_path / "locks"

    with acquire_process_lock("sub-llm", lock_dir=lock_dir):
        with pytest.raises(SystemExit) as exc:
            with acquire_process_lock("sub-llm", lock_dir=lock_dir):
                pass
        assert exc.value.code == 1

    # lock released after context
    with acquire_process_lock("sub-llm", lock_dir=lock_dir):
        pass
