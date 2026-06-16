from __future__ import annotations

import os
import sys

import pytest

from app.processes.process_lock import (
    _lock_path,
    acquire,
    acquire_process_lock,
    is_locked,
    locked_names,
    pid_is_alive,
    release,
    stack_lock_name,
    stop_all_command_hint,
)


def test_pid_is_alive_current_process() -> None:
    assert pid_is_alive(os.getpid()) is True


def test_pid_is_alive_dead_process() -> None:
    assert pid_is_alive(999999999) is False


def test_acquire_process_lock_rejects_nested_holder(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    lock_dir = tmp_path / "locks"

    with acquire_process_lock("sub-llm", lock_dir=lock_dir):
        with pytest.raises(SystemExit) as exc:
            with acquire_process_lock("sub-llm", lock_dir=lock_dir):
                pass
        assert exc.value.code == 1

    with acquire_process_lock("sub-llm", lock_dir=lock_dir):
        pass


def test_acquire_and_release(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    pid = os.getpid()
    assert acquire("sub-llm", pid) is True
    assert is_locked("sub-llm") is True
    assert locked_names(["sub-llm", "ingress-ttv-read"]) == ["sub-llm"]
    release("sub-llm", pid)
    assert is_locked("sub-llm") is False


def test_stale_lock_is_replaced(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    lock_dir = tmp_path / "data" / "process-locks"
    lock_dir.mkdir(parents=True)
    (lock_dir / "sub-llm.pid").write_text(str(os.getpid()), encoding="utf-8")
    assert is_locked("sub-llm") is True
    release("sub-llm", os.getpid())
    assert acquire("sub-llm", 99999) is True


def test_acquire_process_lock_allows_same_pid_holder(tmp_path, monkeypatch) -> None:
    """鎖檔已記錄本程序 PID 時，應視為持有者並繼續執行。"""
    monkeypatch.chdir(tmp_path)
    pid = os.getpid()
    assert acquire("sub-llm", pid) is True

    from app.processes.process_lock import acquire_process_lock

    with acquire_process_lock("sub-llm"):
        assert is_locked("sub-llm") is True

    release("sub-llm", pid)


def test_stack_lock_names_use_separate_files(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    lock_dir = tmp_path / "locks"
    llm_name = stack_lock_name("llm")
    ingress_name = stack_lock_name("ingress")
    assert llm_name == "stack_llm"
    assert ingress_name == "stack_ingress"
    assert _lock_path(llm_name, lock_dir) != _lock_path(ingress_name, lock_dir)
    assert acquire(llm_name, 100, lock_dir=lock_dir) is True
    assert acquire(ingress_name, 200, lock_dir=lock_dir) is True
    assert len(list(lock_dir.glob("*.pid"))) == 2
    holder = os.getpid()
    release(llm_name, 100, lock_dir=lock_dir)
    assert acquire(llm_name, holder, lock_dir=lock_dir) is True
    assert acquire(llm_name, holder, lock_dir=lock_dir) is False
    release(llm_name, holder, lock_dir=lock_dir)
    release(ingress_name, 200, lock_dir=lock_dir)


def test_legacy_stack_colon_name_is_sanitized(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    lock_dir = tmp_path / "locks"
    assert _lock_path("stack:llm", lock_dir).name == "stack_llm.pid"
    assert acquire("stack:llm", 100, lock_dir=lock_dir) is True
    assert (lock_dir / "stack_llm.pid").is_file()
    release("stack:llm", 100, lock_dir=lock_dir)


def test_stop_all_command_hint_platform_specific() -> None:
    hint = stop_all_command_hint()
    if sys.platform == "win32":
        assert "stop_all.ps1" in hint
    else:
        assert "stop_all.sh" in hint
