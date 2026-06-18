from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from voice_clone.audio.preprocess import load_sample_audio

if TYPE_CHECKING:
    from voice_clone.stt.worker import OfflineSTTWorker


@dataclass(frozen=True)
class SampleReference:
    audio_path: Path
    text: str
    source_audio_path: Path | None = None


def find_paired_sample_text(sample_path: Path) -> str | None:
    """從舊專案 folder_pairs 格式（audio/ + text/）或同目錄 .txt 讀取參考文字。"""
    stem = sample_path.stem
    candidates = [
        sample_path.with_suffix(".txt"),
    ]
    if sample_path.parent.name == "audio":
        candidates.append(sample_path.parent.parent / "text" / f"{stem}.txt")
    for candidate in candidates:
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8").strip()
            if text:
                return text
    return None


def resolve_sample_reference(
    sample_path: Path,
    *,
    sample_text: str | None = None,
    stt_worker: OfflineSTTWorker | None = None,
) -> SampleReference:
    """從樣本音檔取得推理所需的參考音訊與對應文字。"""
    resolved = sample_path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"找不到樣本音檔：{resolved}")

    if sample_text and sample_text.strip():
        return SampleReference(
            audio_path=resolved,
            text=sample_text.strip(),
            source_audio_path=resolved,
        )

    paired = find_paired_sample_text(resolved)
    if paired:
        return SampleReference(
            audio_path=resolved,
            text=paired,
            source_audio_path=resolved,
        )

    if stt_worker is None:
        raise ValueError(
            "請提供 --sample-text、使用含 text/ 配對檔的錄音目錄，或加上 --stt 自動轉寫"
        )

    audio, sample_rate = load_sample_audio(resolved)
    segment = stt_worker.transcribe_audio(audio, sample_rate)
    if segment is None or not segment.text.strip():
        raise ValueError("無法從樣本音檔轉寫文字，請手動提供 --sample-text")

    return SampleReference(
        audio_path=resolved,
        text=segment.text.strip(),
        source_audio_path=resolved,
    )
