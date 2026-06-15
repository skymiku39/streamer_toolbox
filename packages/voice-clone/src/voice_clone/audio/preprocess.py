from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

from voice_clone.audio.denoise import suppress_noise_for_sample
from voice_clone.audio.trim import trim_silence_edges


def load_sample_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio.astype(np.float32), int(sample_rate)


def preprocess_sample_audio(
    sample_path: Path,
    *,
    cache_dir: Path,
    denoise: bool = True,
    trim_silence: bool = True,
    denoise_hp_hz: float = 100.0,
    denoise_gate_ratio: float = 0.12,
) -> Path:
    """降噪與靜音修剪；結果快取於 cache_dir，避免重複處理。"""
    resolved = sample_path.resolve()
    if not denoise and not trim_silence:
        return resolved

    cache_dir.mkdir(parents=True, exist_ok=True)
    stat = resolved.stat()
    digest = hashlib.sha256(
        f"{resolved}|{stat.st_mtime_ns}|{stat.st_size}|{denoise}|{trim_silence}|"
        f"{denoise_hp_hz}|{denoise_gate_ratio}".encode()
    ).hexdigest()[:16]
    cached = cache_dir / f"{resolved.stem}_{digest}.wav"
    if cached.exists():
        return cached

    audio, sample_rate = load_sample_audio(resolved)
    if denoise:
        audio = suppress_noise_for_sample(
            audio,
            sample_rate,
            hp_cutoff_hz=denoise_hp_hz,
            gate_ratio=denoise_gate_ratio,
        )
    if trim_silence:
        audio = trim_silence_edges(audio, sample_rate)
    if audio.size == 0:
        raise ValueError(f"前處理後音訊為空：{resolved}")

    sf.write(cached, audio, sample_rate)
    return cached


def clear_preprocess_cache(cache_dir: Path) -> None:
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
