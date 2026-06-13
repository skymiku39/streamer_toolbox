from __future__ import annotations

import os
import sys
from pathlib import Path

from tts.file_synthesizer import FileVoiceSynthesizer
from tts.noop import NoOpTtsEngine
from tts.protocol import TtsEngine
from tts.synthesize import VoiceSynthesizer


def create_tts_engine(backend: str | None = None) -> TtsEngine:
    """依 backend 或環境變數 TTS_ENGINE 建立引擎。

    支援：auto、noop、sapi5
    """
    resolved = (backend or os.environ.get("TTS_ENGINE", "auto")).strip().lower()
    if resolved == "auto":
        resolved = "sapi5" if sys.platform == "win32" else "noop"

    if resolved == "noop":
        return NoOpTtsEngine()
    if resolved == "sapi5":
        from tts.sapi5 import Sapi5TtsEngine

        return Sapi5TtsEngine()

    raise ValueError(f"unsupported TTS_ENGINE: {resolved!r}")


def create_voice_synthesizer(
    backend: str | None = None,
    *,
    output_dir: Path | None = None,
) -> VoiceSynthesizer:
    """依 VOICE_SYNTH_ENGINE 建立角色語音合成器。

    支援：file（預設）、auto（同 file）
    """
    resolved = (backend or os.environ.get("VOICE_SYNTH_ENGINE", "auto")).strip().lower()
    if resolved in {"auto", "file"}:
        target = output_dir or Path(os.environ.get("VOICE_OUTPUT_DIR", "data/character_voice"))
        return FileVoiceSynthesizer(target)

    raise ValueError(f"unsupported VOICE_SYNTH_ENGINE: {resolved!r}")
