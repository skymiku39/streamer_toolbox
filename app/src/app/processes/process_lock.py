from __future__ import annotations

import os
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_LOCK_DIR = Path("data/process-locks")
_thread_held = threading.local()
_WINDOWS_UNSAFE_LOCK_CHARS = frozenset(':\\/*?"<>|')


def _resolve_lock_dir(lock_dir: Path | None) -> Path:
    return lock_dir if lock_dir is not None else _LOCK_DIR


def _sanitize_lock_name(process_name: str) -> str:
    """Windows 不允許 `:` 等字元；`stack:llm` 會變成 ADS 檔 `stack`，導致鎖失效。"""
    safe = process_name.replace("/", "_").replace("\\", "_")
    for char in _WINDOWS_UNSAFE_LOCK_CHARS:
        safe = safe.replace(char, "_")
    return safe.strip("_") or "unnamed"


def stack_lock_name(stack: str) -> str:
    return _sanitize_lock_name(f"stack_{stack.strip().lower()}")


def _lock_path(process_name: str, lock_dir: Path | None = None) -> Path:
    safe = _sanitize_lock_name(process_name)
    return (_resolve_lock_dir(lock_dir) / f"{safe}.pid").resolve()


def _held_names() -> set[str]:
    held = getattr(_thread_held, "names", None)
    if held is None:
        held = set()
        _thread_held.names = held
    return held


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        process_query_limited = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
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
    """原子建立 lock 檔；若已有存活持有者則回傳 False。"""
    base = _resolve_lock_dir(lock_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = _lock_path(process_name, lock_dir)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        holder = _locked_pid(process_name, lock_dir=lock_dir)
        if holder is None:
            return acquire(process_name, pid, lock_dir=lock_dir)
        return False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(pid))
    except OSError:
        path.unlink(missing_ok=True)
        return False
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
    held = _held_names()
    if process_name in held:
        print(
            f"process '{process_name}' 已在目前程序中持有鎖。"
            f"請先 Ctrl+C 關閉舊程序，或執行 scripts/stop_all.ps1",
            file=sys.stderr,
        )
        raise SystemExit(1)

    holder = _locked_pid(process_name, lock_dir=lock_dir)
    if holder is not None and holder != pid:
        holder_text = f"（PID {holder}）"
        print(
            f"process '{process_name}' 已在執行{holder_text}。"
            f"請先 Ctrl+C 關閉舊程序，或執行 scripts/stop_all.ps1",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if holder is None and not acquire(process_name, pid, lock_dir=lock_dir):
        holder = _locked_pid(process_name, lock_dir=lock_dir)
        if holder is not None and holder != pid:
            holder_text = f"（PID {holder}）"
            print(
                f"process '{process_name}' 已在執行{holder_text}。"
                f"請先 Ctrl+C 關閉舊程序，或執行 scripts/stop_all.ps1",
                file=sys.stderr,
            )
            raise SystemExit(1)

    held.add(process_name)
    try:
        yield
    finally:
        held.discard(process_name)
        release(process_name, pid, lock_dir=lock_dir)
