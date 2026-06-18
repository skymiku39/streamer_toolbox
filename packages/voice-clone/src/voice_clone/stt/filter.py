"""STT 輸入過濾：靜音閘與 Whisper 幻覺文字偵測（移植自 streamer_toolbox safety/stt_input）。"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import Any

_STRUCTURE_PATTERNS = re.compile(
    r"|".join(
        (
            r"字幕\s*(by|由|志愿者|志願者|提供者|製作人|提供)",
            r"subtitle",
            r"subtitles?\s+by",
            r"thank\s+you\s+for\s+(watching|listening)",
            r"thanks\s+for\s+(watching|listening)",
            r"amara\.org",
            r"\bwww\.",
            r"https?://",
            r"^[\s\d\.,，。！!？?…·\-—\[\]()]+$",
            r"^\[?\s*(music|applause|silence)\s*\]?$",
        )
    ),
    re.IGNORECASE,
)

_FILLER_ONLY = re.compile(
    r"^(嗯+|啊{2,}|呃{2,}|哦{2,}|噢{2,}|额{2,}|額{2,}|恩{2,})[\s\.。,，!！?？…]*$",
)

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

_DEFAULT_BLOCKLIST = (
    "請訂閱",
    "感謝收看",
    "謝謝觀看",
    "thanks for watching",
    "subscribe",
)


def pcm_rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    count = len(pcm) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", pcm[: count * 2])
    mean_sq = sum(sample * sample for sample in samples) / count
    return (mean_sq**0.5) / 32768.0


def float32_rms(audio) -> float:
    import numpy as np

    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio))))


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _contains_cjk(text: str) -> bool:
    return _CJK_RE.search(text) is not None


def _is_short_latin_noise(text: str) -> bool:
    raw = _normalize_for_match(text)
    if len(raw) > 6 or _contains_cjk(raw):
        return False
    letters = sum(1 for char in raw if char.isalnum())
    return letters <= 2


def _is_repetitive_hallucination(text: str) -> bool:
    normalized = _normalize_for_match(text)
    if len(normalized) < 12:
        return False
    parts = normalized.split()
    if len(parts) >= 3 and len(set(parts)) == 1:
        return True
    for width in (4, 5, 6, 8):
        if len(normalized) < width * 2:
            continue
        for index in range(0, len(normalized) - width):
            chunk = normalized[index : index + width]
            if chunk.strip() and normalized.count(chunk) >= 3:
                return True
    return False


def _matches_blocklist(text: str, phrases: tuple[str, ...]) -> bool:
    normalized = _normalize_for_match(text).lower()
    if not normalized:
        return False
    for phrase in phrases:
        candidate = phrase.strip().lower()
        if candidate and candidate in normalized:
            return True
    return False


def is_hallucination_text(text: str, *, blocklist: tuple[str, ...] | None = None) -> bool:
    raw = _normalize_for_match(text)
    if not raw:
        return True
    if len(raw) < 2:
        if len(raw) == 1 and _contains_cjk(raw) and raw != "嗯":
            return False
        return True
    if _FILLER_ONLY.match(raw):
        return True
    if _STRUCTURE_PATTERNS.search(raw):
        return True
    if _is_repetitive_hallucination(text):
        return True
    phrases = blocklist if blocklist is not None else _DEFAULT_BLOCKLIST
    if _matches_blocklist(text, phrases):
        return True
    if _is_short_latin_noise(text):
        return True
    return False


def accept_whisper_segment(
    seg: Any,
    *,
    no_speech_threshold: float,
    log_prob_threshold: float,
    blocklist: tuple[str, ...] | None = None,
) -> bool:
    text = (getattr(seg, "text", None) or "").strip()
    if not text or is_hallucination_text(text, blocklist=blocklist):
        return False
    nsp = getattr(seg, "no_speech_prob", 0.0) or 0.0
    alp = getattr(seg, "avg_logprob", 0.0) or 0.0
    if nsp > no_speech_threshold and alp < log_prob_threshold:
        return False
    if nsp > 0.85:
        return False
    return True


@dataclass(frozen=True)
class SttInputFilter:
    rms_gate: float = 0.01
    filter_hallucinations: bool = True
    no_speech_threshold: float = 0.6
    log_prob_threshold: float = -1.0
    blocklist: tuple[str, ...] = _DEFAULT_BLOCKLIST

    def is_silent_pcm(self, pcm: bytes) -> bool:
        return pcm_rms(pcm) < self.rms_gate

    def is_silent_audio(self, audio) -> bool:
        return float32_rms(audio) < self.rms_gate

    def accept_text(self, text: str) -> bool:
        if not self.filter_hallucinations:
            return bool(text.strip())
        return not is_hallucination_text(text, blocklist=self.blocklist)

    def accept_segment(self, seg: Any) -> bool:
        if not self.filter_hallucinations:
            return bool((getattr(seg, "text", None) or "").strip())
        return accept_whisper_segment(
            seg,
            no_speech_threshold=self.no_speech_threshold,
            log_prob_threshold=self.log_prob_threshold,
            blocklist=self.blocklist,
        )
