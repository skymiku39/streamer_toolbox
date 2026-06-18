"""STT 輸入過濾：靜音閘與 Whisper 幻覺文字偵測。

對照 llm_twitchat ingest/stt_filters.py；黑名單以結構化 pattern 為主，可後續擴充詞表檔。
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from safety.audio_spectrum import float32_rms, lacks_clear_speech, lacks_clear_speech_audio

if TYPE_CHECKING:
    from collections.abc import Sequence

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

# 連續語助詞；單一「啊／呃」可能是真實口語，僅攔截重複或 Whisper 常見的「嗯」
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

_GAMING_LATIN_ALLOW = frozenset(
    {"gg", "ok", "hp", "mp", "dps", "afk", "brb", "lol", "rip", "fps", "pvp", "pve"},
)


def pcm_rms(pcm: bytes) -> float:
    """int16 PCM 的 RMS，範圍約 0～1。"""
    if len(pcm) < 2:
        return 0.0
    count = len(pcm) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", pcm[: count * 2])
    mean_sq = sum(sample * sample for sample in samples) / count
    return (mean_sq**0.5) / 32768.0


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _contains_cjk(text: str) -> bool:
    return _CJK_RE.search(text) is not None


def _is_short_latin_noise(text: str) -> bool:
    """短 ASCII 雜訊（如 'ok'）；含中文時不套用。"""
    raw = _normalize_for_match(text)
    if raw.lower() in _GAMING_LATIN_ALLOW:
        return False
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


def _matches_blocklist(text: str, phrases: Sequence[str]) -> bool:
    normalized = _normalize_for_match(text).lower()
    if not normalized:
        return False
    for phrase in phrases:
        candidate = phrase.strip().lower()
        if candidate and candidate in normalized:
            return True
    return False


def _is_zh_stream_latin_hallucination(text: str) -> bool:
    """中文直播 STT 常見的純英文幻覺（如 Now time）。"""
    raw = _normalize_for_match(text)
    if not raw or _contains_cjk(raw):
        return False
    if not any(char.isalpha() for char in raw):
        return False
    words = [word.lower() for word in re.findall(r"[a-zA-Z]+", raw)]
    if not words:
        return False
    if all(word in _GAMING_LATIN_ALLOW for word in words):
        return False
    if _matches_blocklist(text, _DEFAULT_BLOCKLIST):
        return True
    if len(words) >= 2:
        return True
    return len(words[0]) >= 5 and words[0] not in _GAMING_LATIN_ALLOW


def is_hallucination_text(
    text: str,
    *,
    blocklist: Sequence[str] | None = None,
    language: str | None = None,
) -> bool:
    raw = _normalize_for_match(text)
    if not raw:
        return True
    if len(raw) < 2:
        # 單一 CJK 字（啊、欸等）可能是真實口語；「嗯」仍視為常見幻覺
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
    if (language or "zh") == "zh" and _is_zh_stream_latin_hallucination(text):
        return True
    return False


def accept_whisper_segment(
    seg: Any,
    *,
    no_speech_threshold: float,
    log_prob_threshold: float,
    blocklist: Sequence[str] | None = None,
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
    """STT chunk 輸入閘門設定。"""

    rms_gate: float = 0.01
    filter_hallucinations: bool = True
    hallucination_rms_gate: float = 0.02
    hallucination_speech_band_min: float = 0.25
    hallucination_spectral_flatness_max: float = 0.35
    sample_rate: int = 16000
    no_speech_threshold: float = 0.6
    log_prob_threshold: float = -1.0
    blocklist: tuple[str, ...] = _DEFAULT_BLOCKLIST

    def is_silent(self, pcm: bytes) -> bool:
        return pcm_rms(pcm) < self.rms_gate

    def is_silent_audio(self, audio) -> bool:
        """float32 音訊的靜音判斷（供已解碼為 numpy 波形的呼叫端使用）。"""
        return float32_rms(audio) < self.rms_gate

    def should_apply_hallucination_filter(self, pcm: bytes) -> bool:
        """FFT 頻譜 + RMS：chunk 不像語音時才套用幻覺過濾。"""
        if not self.filter_hallucinations:
            return False
        return lacks_clear_speech(
            pcm,
            sample_rate=self.sample_rate,
            rms_gate=self.hallucination_rms_gate,
            max_spectral_flatness=self.hallucination_spectral_flatness_max,
            min_speech_band_ratio=self.hallucination_speech_band_min,
        )

    def should_apply_hallucination_filter_audio(self, audio) -> bool:
        if not self.filter_hallucinations:
            return False
        return lacks_clear_speech_audio(
            audio,
            sample_rate=self.sample_rate,
            rms_gate=self.hallucination_rms_gate,
            max_spectral_flatness=self.hallucination_spectral_flatness_max,
            min_speech_band_ratio=self.hallucination_speech_band_min,
        )

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
