from __future__ import annotations

import wave
from pathlib import Path

from pkg_tts.synthesize import SynthesizedAudio

SAMPLE_RATE = 22050
CHANNELS = 1
SAMPLE_WIDTH = 2
MS_PER_CHAR = 120
MIN_DURATION_MS = 500


def estimate_duration_ms(text: str) -> int:
    return max(MIN_DURATION_MS, len(text.strip()) * MS_PER_CHAR)


class FileVoiceSynthesizer:
    """將文字寫入 WAV 檔（佔位／測試用；可替換為雲端或 SAPI5 檔案輸出）。"""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def synthesize(self, text: str, *, turn_id: str, language: str = "zh-TW") -> SynthesizedAudio:
        del language  # 預留給多語系引擎
        duration_ms = estimate_duration_ms(text)
        path = self._output_dir / f"{turn_id}.wav"
        self._write_silent_wav(path, duration_ms)
        return SynthesizedAudio(path=str(path.resolve()), duration_ms=duration_ms)

    def _write_silent_wav(self, path: Path, duration_ms: int) -> None:
        frame_count = int(SAMPLE_RATE * duration_ms / 1000)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(SAMPLE_WIDTH)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(b"\x00" * frame_count * SAMPLE_WIDTH)
