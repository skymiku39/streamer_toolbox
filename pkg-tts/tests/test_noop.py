from __future__ import annotations

from pkg_tts.noop import NoOpTtsEngine


def test_noop_without_record_does_not_store() -> None:
    engine = NoOpTtsEngine(record=False)
    engine.speak("hello")
    assert engine.spoken == ()


def test_noop_with_record_stores_in_order() -> None:
    engine = NoOpTtsEngine(record=True)
    engine.speak("first")
    engine.speak("second")
    assert engine.spoken == ("first", "second")
