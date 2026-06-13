from __future__ import annotations

import os

from app.processes.process_lock import acquire, is_locked, locked_names, release


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
