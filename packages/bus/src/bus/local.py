from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable


class LocalEventBus:
    """程序內記憶體 Event Bus，用於模組間解耦通訊（不經 RabbitMQ）。"""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)

    def publish(self, topic: str, payload: dict) -> None:
        for handler in list(self._handlers.get(topic, [])):
            handler(payload)

    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> None:
        if handler not in self._handlers[topic]:
            self._handlers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[dict], None]) -> None:
        if handler in self._handlers[topic]:
            self._handlers[topic].remove(handler)

    def clear(self) -> None:
        self._handlers.clear()
