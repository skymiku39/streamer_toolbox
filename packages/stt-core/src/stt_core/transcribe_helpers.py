"""Whisper 轉寫共用邏輯（串流 / 離線 worker）。"""

from __future__ import annotations

import math
from typing import Any

from safety import SttInputFilter

from stt_core.config import SttConfig


def logprob_to_confidence(avg_logprob: float | None) -> float:
    if avg_logprob is None:
        return 0.0
    return min(1.0, max(0.0, math.exp(float(avg_logprob))))


def resolve_initial_prompt(config: SttConfig, *, last_text: str = "") -> str | None:
    parts: list[str] = []
    if config.initial_prompt.strip():
        parts.append(config.initial_prompt.strip())
    if config.carry_prompt and last_text.strip():
        parts.append(last_text.strip()[-120:])
    if not parts:
        return None
    return " ".join(parts)


def build_whisper_kwargs(config: SttConfig, *, initial_prompt: str | None = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "language": config.language or None,
        "vad_filter": config.vad_filter,
        "beam_size": config.beam_size,
        "condition_on_previous_text": config.condition_on_previous_text,
        "no_speech_threshold": config.no_speech_threshold,
        "log_prob_threshold": config.log_prob_threshold,
        "compression_ratio_threshold": config.compression_ratio_threshold,
        "temperature": 0.0,
    }
    if initial_prompt:
        kwargs["initial_prompt"] = initial_prompt
    return kwargs


def collect_whisper_texts(
    segments: Any,
    input_filter: SttInputFilter,
    *,
    apply_hallucination_filter: bool,
) -> tuple[list[str], list[float]]:
    texts: list[str] = []
    confidences: list[float] = []
    for seg in segments:
        if apply_hallucination_filter and not input_filter.accept_segment(seg):
            continue
        text = (getattr(seg, "text", None) or "").strip()
        if not text:
            continue
        if apply_hallucination_filter and not input_filter.accept_text(text):
            continue
        texts.append(text)
        confidences.append(logprob_to_confidence(getattr(seg, "avg_logprob", None)))
    return texts, confidences


def merge_confidence(confidences: list[float]) -> float:
    if not confidences:
        return 0.0
    return sum(confidences) / len(confidences)
