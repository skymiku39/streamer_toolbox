"""Windows 與子程序主控台 UTF-8 設定。"""
from __future__ import annotations

import contextlib
import io
import os
import sys


def _set_windows_console_utf8() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def configure_utf8_stdio() -> None:
    """將目前程序的 stdout/stderr 設為 UTF-8，避免 cp950 亂碼。"""
    if sys.platform == "win32":
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        _set_windows_console_utf8()

    for stream in (sys.stdout, sys.stderr):
        buffer = getattr(stream, "buffer", None)
        if buffer is not None and (
            getattr(stream, "encoding", "").lower().replace("-", "") != "utf8"
        ):
            wrapper = io.TextIOWrapper(
                buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
            if stream is sys.stdout:
                sys.stdout = wrapper
            elif stream is sys.stderr:
                sys.stderr = wrapper
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(Exception):
                reconfigure(encoding="utf-8", errors="replace")


def write_stdio(text: str, *, stream: io.TextIOBase | None = None) -> None:
    """以 UTF-8 寫入主控台（繞過 cp950 TextIOWrapper 限制）。"""
    target = stream or sys.stdout
    data = text.encode("utf-8", errors="replace")
    buffer = getattr(target, "buffer", None)
    if buffer is not None:
        buffer.write(data)
        buffer.flush()
        return
    target.write(text)
    target.flush()


def utf8_subprocess_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """子程序環境：沿用 PYTHONPATH 等，並強制 UTF-8 I/O。"""
    merged = dict(env or os.environ)
    merged.setdefault("PYTHONUTF8", "1")
    merged.setdefault("PYTHONIOENCODING", "utf-8")
    return merged
