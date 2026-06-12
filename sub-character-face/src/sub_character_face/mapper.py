from __future__ import annotations

EMOTION_PRESETS: dict[str, dict[str, float]] = {
    "neutral": {"mouth_smile": 0.0, "eye_open": 1.0},
    "happy": {"mouth_smile": 0.9, "eye_smile": 0.8},
    "angry": {"mouth_smile": -0.3, "brow_down": 0.7},
    "sad": {"mouth_smile": -0.5, "eye_open": 0.7},
    "surprised": {"eye_wide": 0.9, "mouth_open": 0.5},
}


def map_emotion_to_parameters(emotion: str, intensity: float = 1.0) -> dict[str, float]:
    """將 emotion / intensity 映射為 VTS 相容參數。"""
    preset = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS["neutral"])
    clamped = max(0.0, min(1.0, intensity))
    return {key: round(value * clamped, 4) for key, value in preset.items()}
