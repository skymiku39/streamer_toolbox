"""以 .env 載入 SttConfig，驗證 FFT 閘門與 end-to-end STT（開發用）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = Path(__file__).resolve().parent
for rel in ("app/src", "app/src/app/publishers", str(BENCH)):
    p = ROOT / rel if rel != str(BENCH) else BENCH
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=True)

from ingress_twitch_audio.stt_worker import StreamingSTTWorker  # noqa: E402
from safety import SttInputFilter  # noqa: E402
from stt_core import SttConfig  # noqa: E402

from stt_params import (  # noqa: E402
    cer,
    load_pcm,
    normalize_text,
    parse_ground_truth,
    transcribe_file,
)


def verify_fft_gate(audio_dir: Path, gate: SttInputFilter, chunk_seconds: float) -> dict:
    apply_files: list[str] = []
    skip_files: list[str] = []
    silent_files: list[str] = []
    chunk_bytes = int(16000 * 2 * chunk_seconds)
    for mp3 in sorted(audio_dir.glob("*.mp3")):
        pcm = load_pcm(mp3)
        chunks = [pcm[i : i + chunk_bytes] for i in range(0, len(pcm), chunk_bytes)]
        speech_chunks = [c for c in chunks if not gate.is_silent(c)]
        if not speech_chunks:
            silent_files.append(mp3.name)
            continue
        if any(gate.should_apply_hallucination_filter(c) for c in speech_chunks):
            apply_files.append(mp3.name)
        else:
            skip_files.append(mp3.name)
    return {
        "skip": len(skip_files),
        "apply": len(apply_files),
        "silent": len(silent_files),
        "apply_files": apply_files,
    }


def verify_whisper(audio_dir: Path, config: SttConfig, *, limit: int = 0) -> dict:
    files = sorted(audio_dir.glob("*.mp3"))
    if limit > 0:
        files = files[:limit]
    worker = StreamingSTTWorker(config)
    worker._ensure_model()  # noqa: SLF001
    labeled = 0
    exact = 0
    missed = 0
    cer_sum = 0.0
    for path in files:
        ref = parse_ground_truth(path.name)
        if not ref:
            continue
        pcm = load_pcm(path)
        hyp, _ = transcribe_file(worker, pcm, config.chunk_seconds)
        labeled += 1
        if normalize_text(ref) == normalize_text(hyp):
            exact += 1
        if not normalize_text(hyp):
            missed += 1
        cer_sum += cer(ref, hyp)
    return {
        "files": len(files),
        "labeled": labeled,
        "exact_rate": exact / labeled if labeled else 0.0,
        "miss_rate": missed / labeled if labeled else 0.0,
        "mean_cer": cer_sum / labeled if labeled else 0.0,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--limit", type=int, default=0, help="Whisper 最多測幾檔（0=全部）")
    parser.add_argument("--skip-whisper", action="store_true")
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    config = SttConfig.from_env()
    gate = SttInputFilter(
        rms_gate=config.rms_gate,
        filter_hallucinations=config.filter_hallucinations,
        hallucination_rms_gate=config.hallucination_rms_gate,
        hallucination_speech_band_min=config.hallucination_speech_band_min,
        hallucination_spectral_flatness_max=config.hallucination_spectral_flatness_max,
    )

    print("=== .env STT 設定 ===")
    print(
        f"chunk={config.chunk_seconds}s rms_gate={config.rms_gate} "
        f"vad={config.vad_filter} filter={config.filter_hallucinations}"
    )
    print(
        f"nsp={config.no_speech_threshold} logprob={config.log_prob_threshold} "
        f"ctx={config.condition_on_previous_text}"
    )
    print(
        f"hallucination_rms={config.hallucination_rms_gate} "
        f"speech_band={config.hallucination_speech_band_min} "
        f"flatness={config.hallucination_spectral_flatness_max}"
    )

    fft = verify_fft_gate(audio_dir, gate, config.chunk_seconds)
    total = fft["skip"] + fft["apply"] + fft["silent"]
    print(f"\n=== FFT 幻覺閘門（{total} 檔）===")
    print(f"略過 filter（像語音）: {fft['skip']}")
    print(f"套用 filter（不像語音）: {fft['apply']}")
    print(f"全靜音略過: {fft['silent']}")
    if fft["apply_files"]:
        print("套用 filter 的檔:", fft["apply_files"])

    if args.skip_whisper:
        return 0

    print("\n=== Whisper end-to-end（載入 .env 設定）===")
    stats = verify_whisper(audio_dir, config, limit=args.limit)
    print(
        f"labeled={stats['labeled']} exact={stats['exact_rate']:.1%} "
        f"miss={stats['miss_rate']:.1%} mean_cer={stats['mean_cer']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
