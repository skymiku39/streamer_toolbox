from __future__ import annotations

import os
import socket
from contextlib import contextmanager
from typing import Iterator

from voice_clone.config import Settings, get_settings

_BLOCKED = False


def apply_offline_env(settings: Settings | None = None) -> None:
    """設定離線相關環境變數。"""
    settings = settings or get_settings()
    if settings.offline:
        os.environ["VOICE_CLONE_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ.setdefault("HF_DATASETS_OFFLINE", "1")


def enable_network_block() -> None:
    """Fail-fast：阻斷 socket 連線（僅在 VOICE_CLONE_OFFLINE=1 時啟用）。"""
    global _BLOCKED
    if _BLOCKED:
        return

    original_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: object) -> None:
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError(
                f"離線模式禁止網路連線：嘗試連線至 {host!r}。"
                "若需下載模型，請在有網路環境執行 scripts/fetch_models.ps1。"
            )
        original_connect(self, address)

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    _BLOCKED = True


def enforce_offline(settings: Settings | None = None, *, block_network: bool = True) -> None:
    settings = settings or get_settings()
    apply_offline_env(settings)
    if settings.offline and block_network:
        enable_network_block()


@contextmanager
def offline_context(settings: Settings | None = None, *, block_network: bool = False) -> Iterator[None]:
    """CLI 入口使用的離線上下文。"""
    settings = settings or get_settings()
    apply_offline_env(settings)
    if settings.offline and block_network:
        enable_network_block()
    yield
