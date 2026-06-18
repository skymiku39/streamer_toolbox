"""Deprecated re-export shim：STT 降噪請改用 ``from stt_core.denoise import ...``。"""

from stt_core.denoise import spectral_gate, suppress_noise_for_stt
from voice_clone.audio.denoise import (
    highpass_filter,
    suppress_noise,
    suppress_noise_for_sample,
)

__all__ = [
    "highpass_filter",
    "spectral_gate",
    "suppress_noise",
    "suppress_noise_for_sample",
    "suppress_noise_for_stt",
]
