"""Windows 與子程序主控台 UTF-8 設定。"""
from __future__ import annotations

import contextlib
import os
import sys


def configure_utf8_stdio() -> None:
    """將目前程序的 stdout/stderr 設為 UTF-8，避免 cp950 亂碼。"""
    if sys.platform == "win32":
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(Exception):
                reconfigure(encoding="utf-8", errors="replace")


def utf8_subprocess_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """子程序環境：沿用 PYTHONPATH 等，並強制 UTF-8 I/O。"""
    merged = dict(env or os.environ)
    merged.setdefault("PYTHONUTF8", "1")
    merged.setdefault("PYTHONIOENCODING", "utf-8")
    return merged
