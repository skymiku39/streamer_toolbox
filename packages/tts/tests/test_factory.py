from __future__ import annotations

import pytest

from tts import NoOpTtsEngine, create_tts_engine
from tts.protocol import TtsEngine


def test_create_noop_engine() -> None:
    engine = create_tts_engine("noop")
    assert isinstance(engine, NoOpTtsEngine)
    assert isinstance(engine, TtsEngine)


def test_create_auto_non_windows_uses_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tts.factory.sys.platform", "linux")
    engine = create_tts_engine("auto")
    assert isinstance(engine, NoOpTtsEngine)


def test_unsupported_backend_raises() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        create_tts_engine("elevenlabs")
