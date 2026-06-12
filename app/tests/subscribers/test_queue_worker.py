from __future__ import annotations

from pkg_tts.noop import NoOpTtsEngine

from sub_tts.queue_worker import TtsPlaybackQueue


def test_playback_preserves_order() -> None:
    engine = NoOpTtsEngine(record=True)
    queue = TtsPlaybackQueue(engine, cooldown_seconds=0, max_queue_size=10)

    queue.enqueue("one")
    queue.enqueue("two")
    queue.enqueue("three")
    queue.shutdown()

    assert engine.spoken == ("one", "two", "three")


def test_max_queue_drops_oldest() -> None:
    engine = NoOpTtsEngine(record=True)
    queue = TtsPlaybackQueue(engine, cooldown_seconds=0, max_queue_size=2)

    queue.enqueue("first")
    queue.enqueue("second")
    dropped = queue.enqueue("third")
    queue.shutdown()

    assert dropped is False
    assert engine.spoken == ("second", "third")
