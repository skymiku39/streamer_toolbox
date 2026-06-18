"""以檔名文字為 ground truth，評估 STT 參數組合（ingress 管線）。

開發用 benchmark，不納入 CI。音檔目錄以 ``--audio-dir`` 指定，
結果 JSON 預設寫入 ``logs/``（避免汙染 repo 根目錄）。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for rel in ("app/src", "app/src/app/publishers"):
    p = ROOT / rel
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from stt_core import SttConfig, StreamingSTTWorker  # noqa: E402

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2

_PUNCT_RE = re.compile(r"[\s，。！？、…．,.!?;；：:\"\"''「」『』（）()\[\]【】\-—_~～·]+")


def normalize_text(text: str) -> str:
    return _PUNCT_RE.sub("", (text or "").strip().lower())


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    ref = normalize_text(reference)
    hyp = normalize_text(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def parse_ground_truth(filename: str) -> str:
    stem = Path(filename).stem
    parts = stem.split("_", 2)
    if len(parts) < 3:
        return ""
    text = parts[2].strip()
    if text in {"_", "??", "???"} or text.startswith("("):
        return ""
    return text


def load_pcm(path: Path) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("找不到 ffmpeg")
    proc = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    return proc.stdout


def iter_pcm_chunks(pcm: bytes, chunk_seconds: float) -> list[bytes]:
    chunk_bytes = int(SAMPLE_RATE * BYTES_PER_SAMPLE * chunk_seconds)
    if chunk_bytes <= 0:
        return []
    return [pcm[i : i + chunk_bytes] for i in range(0, len(pcm), chunk_bytes)]


def transcribe_file(worker: StreamingSTTWorker, pcm: bytes, chunk_seconds: float) -> tuple[str, dict]:
    chunks = iter_pcm_chunks(pcm, chunk_seconds)
    texts: list[str] = []
    stats = {
        "chunks_total": len(chunks),
        "chunks_silent": 0,
        "chunks_empty": 0,
        "chunks_ok": 0,
    }
    worker.reset_stream_offset(0.0)
    for chunk in chunks:
        seg = worker.transcribe_chunk(chunk)
        if seg is None:
            if worker._input_filter.is_silent(chunk):  # noqa: SLF001
                stats["chunks_silent"] += 1
            else:
                stats["chunks_empty"] += 1
            continue
        stats["chunks_ok"] += 1
        texts.append(seg.text.strip())
    return "".join(texts), stats


@dataclass(frozen=True)
class Preset:
    name: str
    kwargs: dict


def build_presets() -> list[Preset]:
    common = {
        "model_size": "medium",
        "language": "zh",
        "device": "cuda",
        "compute_type": "float16",
        "cpu_threads": 4,
    }
    return [
        Preset(
            "baseline",
            {
                **common,
                "chunk_seconds": 5.0,
                "rms_gate": 0.01,
                "filter_hallucinations": True,
                "vad_filter": True,
                "condition_on_previous_text": False,
                "no_speech_threshold": 0.6,
                "log_prob_threshold": -1.0,
                "compression_ratio_threshold": 2.4,
            },
        ),
        Preset(
            "llm_twitchat",
            {
                **common,
                "chunk_seconds": 4.0,
                "rms_gate": 0.004,
                "filter_hallucinations": True,
                "vad_filter": False,
                "condition_on_previous_text": False,
                "no_speech_threshold": 0.65,
                "log_prob_threshold": -0.8,
                "compression_ratio_threshold": 2.2,
            },
        ),
        Preset(
            "llm_twitchat+ctx",
            {
                **common,
                "chunk_seconds": 4.0,
                "rms_gate": 0.004,
                "filter_hallucinations": True,
                "vad_filter": False,
                "condition_on_previous_text": True,
                "no_speech_threshold": 0.65,
                "log_prob_threshold": -0.8,
                "compression_ratio_threshold": 2.2,
            },
        ),
        Preset(
            "relaxed_filter",
            {
                **common,
                "chunk_seconds": 4.0,
                "rms_gate": 0.004,
                "filter_hallucinations": True,
                "vad_filter": False,
                "condition_on_previous_text": True,
                "no_speech_threshold": 0.7,
                "log_prob_threshold": -1.2,
                "compression_ratio_threshold": 2.4,
            },
        ),
        Preset(
            "no_outer_filter",
            {
                **common,
                "chunk_seconds": 4.0,
                "rms_gate": 0.004,
                "filter_hallucinations": False,
                "vad_filter": False,
                "condition_on_previous_text": True,
                "no_speech_threshold": 0.65,
                "log_prob_threshold": -0.8,
                "compression_ratio_threshold": 2.2,
            },
        ),
    ]


@dataclass
class FileResult:
    file: str
    reference: str
    hypothesis: str
    cer: float
    exact: bool
    missed: bool
    chunk_stats: dict


@dataclass
class PresetSummary:
    preset: str
    files: int
    labeled_files: int
    mean_cer: float
    exact_rate: float
    miss_rate: float
    mean_chunks_silent: float
    mean_chunks_empty: float


def evaluate_preset(
    preset: Preset,
    files: list[Path],
    *,
    shared_model: object | None = None,
) -> tuple[PresetSummary, list[FileResult]]:
    config = SttConfig(**preset.kwargs)
    loader = (lambda: shared_model) if shared_model is not None else None
    worker = StreamingSTTWorker(config, model_loader=loader)
    worker._ensure_model()  # noqa: SLF001

    results: list[FileResult] = []
    for path in files:
        reference = parse_ground_truth(path.name)
        pcm = load_pcm(path)
        hypothesis, chunk_stats = transcribe_file(worker, pcm, config.chunk_seconds)
        c = cer(reference, hypothesis) if reference else 0.0
        exact = bool(reference) and normalize_text(reference) == normalize_text(hypothesis)
        missed = bool(reference) and not normalize_text(hypothesis)
        results.append(
            FileResult(
                file=path.name,
                reference=reference,
                hypothesis=hypothesis,
                cer=c,
                exact=exact,
                missed=missed,
                chunk_stats=chunk_stats,
            ),
        )

    labeled = [r for r in results if r.reference]
    if not labeled:
        summary = PresetSummary(preset.name, len(results), 0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return summary, results

    summary = PresetSummary(
        preset=preset.name,
        files=len(results),
        labeled_files=len(labeled),
        mean_cer=sum(r.cer for r in labeled) / len(labeled),
        exact_rate=sum(1 for r in labeled if r.exact) / len(labeled),
        miss_rate=sum(1 for r in labeled if r.missed) / len(labeled),
        mean_chunks_silent=sum(r.chunk_stats["chunks_silent"] for r in labeled) / len(labeled),
        mean_chunks_empty=sum(r.chunk_stats["chunks_empty"] for r in labeled) / len(labeled),
    )
    return summary, results


def _default_output() -> Path:
    return ROOT / "logs" / "benchmark_stt_params.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="STT 參數基準測試（檔名 = ground truth）")
    parser.add_argument("--audio-dir", required=True, help="含 mp3 的音檔目錄")
    parser.add_argument("--limit", type=int, default=0, help="最多測幾個檔（0=全部）")
    parser.add_argument("--preset", default="", help="只跑單一 preset 名稱")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="結果 JSON 路徑（預設 logs/benchmark_stt_params.json）",
    )
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    files = sorted(audio_dir.glob("*.mp3"))
    if args.limit > 0:
        files = files[: args.limit]
    if not files:
        print(f"找不到 mp3：{audio_dir}", file=sys.stderr)
        return 1

    presets = build_presets()
    if args.preset:
        presets = [p for p in presets if p.name == args.preset]
        if not presets:
            print(f"未知 preset：{args.preset}", file=sys.stderr)
            return 1

    warm_config = SttConfig(**presets[0].kwargs)
    warm_worker = StreamingSTTWorker(warm_config)
    shared_model = warm_worker._ensure_model()  # noqa: SLF001

    summaries: list[PresetSummary] = []
    detail: list[dict] = []
    for preset in presets:
        t0 = time.time()
        summary, results = evaluate_preset(preset, files, shared_model=shared_model)
        elapsed = round(time.time() - t0, 1)
        summaries.append(summary)

        worst = sorted(
            [r for r in results if r.reference],
            key=lambda r: (r.missed, r.cer),
            reverse=True,
        )[:5]
        detail.append(
            {
                **asdict(summary),
                "elapsed_sec": elapsed,
                "config": preset.kwargs,
                "worst_samples": [
                    {
                        "file": w.file,
                        "reference": w.reference,
                        "hypothesis": w.hypothesis,
                        "cer": round(w.cer, 4),
                        "missed": w.missed,
                        "chunk_stats": w.chunk_stats,
                    }
                    for w in worst
                ],
            },
        )
        print(
            f"[{preset.name}] CER={summary.mean_cer:.3f} "
            f"exact={summary.exact_rate:.1%} miss={summary.miss_rate:.1%} "
            f"silent={summary.mean_chunks_silent:.2f} empty={summary.mean_chunks_empty:.2f} "
            f"({elapsed}s)",
            flush=True,
        )

    best = min(summaries, key=lambda s: (s.miss_rate, s.mean_cer, -s.exact_rate))

    output = args.output or _default_output()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "audio_dir": str(audio_dir),
                "file_count": len(files),
                "best": asdict(best),
                "ranking": [asdict(s) for s in summaries],
                "detail": detail,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nBest preset: {best.preset}", flush=True)
    print(f"結果已寫入 {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
