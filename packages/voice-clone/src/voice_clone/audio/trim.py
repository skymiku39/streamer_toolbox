from __future__ import annotations

import numpy as np

DEFAULT_START_THRESHOLD_DB = -40.0
DEFAULT_STOP_THRESHOLD_DB = -50.0


def _db_to_linear(db: float) -> float:
    return 10 ** (db / 20.0)


def trim_silence_edges(
    audio: np.ndarray,
    sample_rate: int,
    *,
    start_threshold_db: float = DEFAULT_START_THRESHOLD_DB,
    stop_threshold_db: float = DEFAULT_STOP_THRESHOLD_DB,
    window_ms: float = 20.0,
    pad_ms: float = 50.0,
) -> np.ndarray:
    """修剪頭尾靜音，保留中間語音段落。"""
    if audio.size == 0:
        return audio
    mono = audio.astype(np.float32)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)

    window = max(1, int(sample_rate * window_ms / 1000.0))
    pad = int(sample_rate * pad_ms / 1000.0)
    start_thr = _db_to_linear(start_threshold_db)
    stop_thr = _db_to_linear(stop_threshold_db)

    def frame_rms(start: int) -> float:
        chunk = mono[start : start + window]
        if chunk.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(chunk))))

    start_idx = 0
    for idx in range(0, len(mono), window):
        if frame_rms(idx) >= start_thr:
            start_idx = max(0, idx - pad)
            break

    end_idx = len(mono)
    for idx in range(len(mono) - window, 0, -window):
        if frame_rms(idx) >= stop_thr:
            end_idx = min(len(mono), idx + window + pad)
            break

    if end_idx <= start_idx:
        return mono
    return mono[start_idx:end_idx].astype(np.float32)
