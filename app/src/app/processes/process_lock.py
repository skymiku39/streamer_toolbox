from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_LOCK_DIR = Path("data/process-locks")


def _resolve_lock_dir(lock_dir: Path | None) -> Path:
    return lock_dir if lock_dir is not None else _LOCK_DIR


def _lock_path(process_name: str, lock_dir: Path | None = None) -> Path:
    safe = process_name.replace("/", "_").replace("\\", "_")
    return (_resolve_lock_dir(lock_dir) / f"{safe}.pid").resolve()


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def is_locked(process_name: str, *, lock_dir: Path | None = None) -> bool:
    path = _lock_path(process_name, lock_dir)
    if not path.is_file():
        return False
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        path.unlink(missing_ok=True)
        return False
    if pid_is_alive(pid):
        return True
    path.unlink(missing_ok=True)
    return False


def _locked_pid(process_name: str, *, lock_dir: Path | None = None) -> int | None:
    path = _lock_path(process_name, lock_dir)
    if not path.is_file():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        path.unlink(missing_ok=True)
        return None
    if pid_is_alive(pid):
        return pid
    path.unlink(missing_ok=True)
    return None


def acquire(process_name: str, pid: int, *, lock_dir: Path | None = None) -> bool:
    base = _resolve_lock_dir(lock_dir)
    base.mkdir(parents=True, exist_ok=True)
    if is_locked(process_name, lock_dir=lock_dir):
        return False
    _lock_path(process_name, lock_dir).write_text(str(pid), encoding="utf-8")
    return True


def release(process_name: str, pid: int | None = None, *, lock_dir: Path | None = None) -> None:
    path = _lock_path(process_name, lock_dir)
    if not path.is_file():
        return
    if pid is not None:
        try:
            locked_pid = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
            return
        if locked_pid != pid:
            return
    path.unlink(missing_ok=True)


def locked_names(process_names: list[str], *, lock_dir: Path | None = None) -> list[str]:
    return [name for name in process_names if is_locked(name, lock_dir=lock_dir)]


@contextmanager
def acquire_process_lock(
    process_name: str,
    *,
    lock_dir: Path | None = None,
) -> Iterator[None]:
    pid = os.getpid()
    if not acquire(process_name, pid, lock_dir=lock_dir):
        holder = _locked_pid(process_name, lock_dir=lock_dir)
        holder_text = f"（PID {holder}）" if holder is not None else ""
        print(
            f"process '{process_name}' 已在執行{holder_text}。"
            f"請先 Ctrl+C 關閉舊程序，或執行 scripts/stop_all.ps1",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        yield
    finally:
        release(process_name, pid, lock_dir=lock_dir)
