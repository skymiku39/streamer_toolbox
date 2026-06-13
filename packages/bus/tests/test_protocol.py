from bus import EventBus


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []
        self.handlers: dict[str, list] = {}

    def publish(self, topic: str, payload: dict) -> None:
        self.published.append((topic, payload))
        for handler in self.handlers.get(topic, []):
            handler(payload)

    def subscribe(self, topic: str, handler) -> None:
        self.handlers.setdefault(topic, []).append(handler)


def test_event_bus_protocol_is_structural() -> None:
    bus: EventBus = _FakeBus()
    received: list[dict] = []
    bus.subscribe("chat.message", received.append)
    payload = {"content": "hello"}
    bus.publish("chat.message", payload)
    assert received == [payload]
