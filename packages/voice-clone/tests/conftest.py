from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_wav(fixtures_dir: Path) -> Path:
    target = fixtures_dir / "sample.wav"
    if not target.exists():
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        sr = 32000
        t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
        audio = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        sf.write(target, audio, sr)
    return target
