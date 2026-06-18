from bus import LocalEventBus


def test_publish_delivers_to_subscriber() -> None:
    bus = LocalEventBus()
    received: list[dict] = []
    bus.subscribe("demo.topic", received.append)

    payload = {"value": 1}
    bus.publish("demo.topic", payload)

    assert received == [payload]


def test_publish_to_topic_without_subscriber_is_noop() -> None:
    bus = LocalEventBus()
    bus.publish("no.subscriber", {"value": 1})  # 不應拋例外


def test_subscribe_is_idempotent_for_same_handler() -> None:
    bus = LocalEventBus()
    calls: list[dict] = []

    def handler(payload: dict) -> None:
        calls.append(payload)

    bus.subscribe("demo.topic", handler)
    bus.subscribe("demo.topic", handler)
    bus.publish("demo.topic", {"value": 1})

    assert len(calls) == 1


def test_multiple_handlers_each_receive_payload() -> None:
    bus = LocalEventBus()
    first: list[dict] = []
    second: list[dict] = []
    bus.subscribe("demo.topic", first.append)
    bus.subscribe("demo.topic", second.append)

    bus.publish("demo.topic", {"value": 1})

    assert first == [{"value": 1}]
    assert second == [{"value": 1}]


def test_unsubscribe_stops_delivery() -> None:
    bus = LocalEventBus()
    received: list[dict] = []
    bus.subscribe("demo.topic", received.append)
    bus.unsubscribe("demo.topic", received.append)

    bus.publish("demo.topic", {"value": 1})

    assert received == []


def test_unsubscribe_unknown_handler_is_noop() -> None:
    bus = LocalEventBus()
    bus.unsubscribe("demo.topic", lambda _payload: None)  # 不應拋例外


def test_clear_removes_all_handlers() -> None:
    bus = LocalEventBus()
    received: list[dict] = []
    bus.subscribe("demo.topic", received.append)
    bus.clear()

    bus.publish("demo.topic", {"value": 1})

    assert received == []


def test_handler_unsubscribing_during_publish_does_not_skip_others() -> None:
    """publish 對 handler 快照迭代：某 handler 取消訂閱不影響本輪其他 handler。"""
    bus = LocalEventBus()
    order: list[str] = []

    def first(_payload: dict) -> None:
        order.append("first")
        bus.unsubscribe("demo.topic", second)

    def second(_payload: dict) -> None:
        order.append("second")

    bus.subscribe("demo.topic", first)
    bus.subscribe("demo.topic", second)
    bus.publish("demo.topic", {"value": 1})

    assert order == ["first", "second"]
