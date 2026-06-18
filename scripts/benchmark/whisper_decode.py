"""Whisper 解碼參數掃描（固定關閉外層 filter，檔名 = ground truth）。

開發用 benchmark，不納入 CI。結果 JSON 預設寫入 ``logs/``。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = Path(__file__).resolve().parent
for p in (ROOT / "app/src", ROOT / "app/src/app/publishers", BENCHMARK_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from stt_params import (  # noqa: E402
    cer,
    iter_pcm_chunks,
    load_pcm,
    normalize_text,
    parse_ground_truth,
)

ANCHOR = {
    "vad_filter": False,
    "condition_on_previous_text": True,
    "beam_size": 1,
    "no_speech_threshold": 0.65,
    "log_prob_threshold": -0.8,
    "compression_ratio_threshold": 2.2,
    "temperature": 0.0,
    "language": "zh",
}

SWEEPS: dict[str, list] = {
    "vad_filter": [True, False],
    "condition_on_previous_text": [True, False],
    "beam_size": [1, 3, 5],
    "no_speech_threshold": [0.4, 0.5, 0.6, 0.65, 0.75, 0.85],
    "log_prob_threshold": [-1.5, -1.2, -1.0, -0.8, -0.6],
    "compression_ratio_threshold": [1.8, 2.0, 2.2, 2.4, 2.6, 3.0],
}

CHUNK_SECONDS = 4.0


@dataclass(frozen=True)
class WhisperParams:
    vad_filter: bool
    condition_on_previous_text: bool
    beam_size: int
    no_speech_threshold: float
    log_prob_threshold: float
    compression_ratio_threshold: float
    temperature: float
    language: str

    def label(self) -> str:
        return (
            f"vad={int(self.vad_filter)} ctx={int(self.condition_on_previous_text)} "
            f"beam={self.beam_size} nsp={self.no_speech_threshold} "
            f"lp={self.log_prob_threshold} cr={self.compression_ratio_threshold}"
        )

    def to_transcribe_kwargs(self) -> dict:
        return {
            "language": self.language or None,
            "vad_filter": self.vad_filter,
            "beam_size": self.beam_size,
            "condition_on_previous_text": self.condition_on_previous_text,
            "no_speech_threshold": self.no_speech_threshold,
            "log_prob_threshold": self.log_prob_threshold,
            "compression_ratio_threshold": self.compression_ratio_threshold,
            "temperature": self.temperature,
        }


@dataclass
class SweepSummary:
    sweep_key: str
    sweep_value: str
    mean_cer: float
    exact_rate: float
    miss_rate: float
    params: dict


def build_oat_variants() -> list[tuple[str, str, WhisperParams]]:
    base = WhisperParams(**ANCHOR)
    variants: list[tuple[str, str, WhisperParams]] = [("anchor", "anchor", base)]
    for key, values in SWEEPS.items():
        for value in values:
            variants.append((key, str(value), replace(base, **{key: value})))
    return variants


def build_combo_variant(best_by_key: dict[str, object]) -> WhisperParams:
    merged = {**ANCHOR, **best_by_key}
    return WhisperParams(**merged)  # type: ignore[arg-type]


def transcribe_file(model: object, pcm: bytes, params: WhisperParams) -> str:
    chunks = iter_pcm_chunks(pcm, CHUNK_SECONDS)
    texts: list[str] = []
    for chunk in chunks:
        audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        if audio.size == 0:
            continue
        segments, _info = model.transcribe(audio, **params.to_transcribe_kwargs())
        part = "".join((seg.text or "").strip() for seg in segments)
        if part:
            texts.append(part)
    return "".join(texts)


def evaluate_variant(
    model: object,
    files: list[Path],
    params: WhisperParams,
    *,
    pcm_cache: dict[str, bytes] | None = None,
) -> tuple[float, float, float]:
    labeled_cers: list[float] = []
    exact = 0
    missed = 0
    labeled = 0
    for path in files:
        reference = parse_ground_truth(path.name)
        if not reference:
            continue
        labeled += 1
        if pcm_cache is not None:
            pcm = pcm_cache[path.name]
        else:
            pcm = load_pcm(path)
        hypothesis = transcribe_file(model, pcm, params)
        labeled_cers.append(cer(reference, hypothesis))
        if not normalize_text(hypothesis):
            missed += 1
        elif normalize_text(reference) == normalize_text(hypothesis):
            exact += 1
    if labeled == 0:
        return 0.0, 0.0, 0.0
    return (
        sum(labeled_cers) / labeled,
        exact / labeled,
        missed / labeled,
    )


def load_model() -> object:
    from faster_whisper import WhisperModel

    return WhisperModel("medium", device="cuda", compute_type="float16")


def _default_output() -> Path:
    return ROOT / "logs" / "benchmark_whisper_decode.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Whisper 解碼參數 OAT 掃描")
    parser.add_argument("--audio-dir", required=True, help="含 mp3 的音檔目錄")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="結果 JSON 路徑（預設 logs/benchmark_whisper_decode.json）",
    )
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    files = sorted(audio_dir.glob("*.mp3"))
    if args.limit > 0:
        files = files[: args.limit]
    if not files:
        print(f"找不到 mp3：{audio_dir}", file=sys.stderr)
        return 1

    print("載入 Whisper medium (cuda)...", flush=True)
    model = load_model()

    print(f"預載 {len(files)} 個音檔 PCM...", flush=True)
    pcm_cache: dict[str, bytes] = {}
    for path in files:
        pcm_cache[path.name] = load_pcm(path)

    variants = build_oat_variants()
    summaries: list[SweepSummary] = []
    by_key: dict[str, list[SweepSummary]] = {k: [] for k in SWEEPS}

    for sweep_key, sweep_value, params in variants:
        t0 = time.time()
        mean_cer, exact_rate, miss_rate = evaluate_variant(
            model, files, params, pcm_cache=pcm_cache,
        )
        elapsed = round(time.time() - t0, 1)
        row = SweepSummary(
            sweep_key=sweep_key,
            sweep_value=sweep_value,
            mean_cer=mean_cer,
            exact_rate=exact_rate,
            miss_rate=miss_rate,
            params=asdict(params),
        )
        summaries.append(row)
        if sweep_key in by_key:
            by_key[sweep_key].append(row)

        print(
            f"[{sweep_key}={sweep_value}] CER={mean_cer:.3f} "
            f"exact={exact_rate:.1%} miss={miss_rate:.1%} ({elapsed}s)",
            flush=True,
        )

    def _parse_sweep_value(key: str, sweep_value: str) -> object:
        sample = SWEEPS[key][0]
        if isinstance(sample, bool):
            return sweep_value == "True"
        if isinstance(sample, int):
            return int(sweep_value)
        return float(sweep_value)

    best_by_key: dict[str, object] = {}
    print("\n=== 各參數最佳值（依 CER → miss → exact）===", flush=True)
    for key, rows in by_key.items():
        best = min(rows, key=lambda r: (r.mean_cer, r.miss_rate, -r.exact_rate))
        best_by_key[key] = _parse_sweep_value(key, best.sweep_value)
        print(
            f"  {key}: {best.sweep_value} "
            f"(CER={best.mean_cer:.3f}, exact={best.exact_rate:.1%}, miss={best.miss_rate:.1%})",
            flush=True,
        )

    combo = build_combo_variant(best_by_key)
    t0 = time.time()
    combo_cer, combo_exact, combo_miss = evaluate_variant(
        model, files, combo, pcm_cache=pcm_cache,
    )
    combo_elapsed = round(time.time() - t0, 1)
    anchor_row = summaries[0]

    output = args.output or _default_output()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "audio_dir": str(audio_dir),
                "file_count": len(files),
                "best_by_key": best_by_key,
                "combo_params": asdict(combo),
                "combo": {
                    "mean_cer": combo_cer,
                    "exact_rate": combo_exact,
                    "miss_rate": combo_miss,
                    "elapsed_sec": combo_elapsed,
                },
                "anchor": asdict(anchor_row),
                "all_variants": [asdict(s) for s in summaries],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n=== 組合驗證 ===", flush=True)
    print(
        f"anchor: CER={anchor_row.mean_cer:.3f} exact={anchor_row.exact_rate:.1%} "
        f"miss={anchor_row.miss_rate:.1%}",
        flush=True,
    )
    print(
        f"combo:  CER={combo_cer:.3f} exact={combo_exact:.1%} miss={combo_miss:.1%} "
        f"({combo_elapsed}s)",
        flush=True,
    )
    print(f"combo params: {combo.label()}", flush=True)
    print(f"結果已寫入 {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
