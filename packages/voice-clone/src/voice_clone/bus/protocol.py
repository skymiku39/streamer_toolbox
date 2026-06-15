from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class EventBus(Protocol):
    def publish(self, topic: str, payload: dict) -> None:
        """發布事件至指定 topic。"""

    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> None:
        """訂閱 topic；handler 收到 payload dict。"""

    def unsubscribe(self, topic: str, handler: Callable[[dict], None]) -> None:
        """取消訂閱。"""
