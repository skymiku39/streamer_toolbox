from bus import LocalEventBus
from voice_clone.events.topics import TOPIC_SYNTHESIS_COMPLETED


def test_bus_publishes_synthesis_event() -> None:
    bus = LocalEventBus()
    received: list[dict] = []
    bus.subscribe(TOPIC_SYNTHESIS_COMPLETED, received.append)
    payload = {"text": "測試", "output_path": "out.wav", "sample_rate": 32000}
    bus.publish(TOPIC_SYNTHESIS_COMPLETED, payload)
    assert received == [payload]
