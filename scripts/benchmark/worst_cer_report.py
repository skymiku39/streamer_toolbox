"""列出 CER 最高的 STT 樣本（開發用）。"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = Path(__file__).resolve().parent
for p in (ROOT / "app/src", ROOT / "app/src/app/publishers", BENCH):
    sys.path.insert(0, str(p))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=True)

from ingress_twitch_audio.config import SttConfig  # noqa: E402
from ingress_twitch_audio.stt_worker import StreamingSTTWorker  # noqa: E402
from stt_params import cer, load_pcm, normalize_text, parse_ground_truth, transcribe_file  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    cfg = SttConfig.from_env()
    worker = StreamingSTTWorker(cfg)
    worker._ensure_model()  # noqa: SLF001

    rows: list[tuple[float, str, str, str, dict]] = []
    for path in sorted(audio_dir.glob("*.mp3")):
        ref = parse_ground_truth(path.name)
        if not ref:
            continue
        pcm = load_pcm(path)
        hyp, stats = transcribe_file(worker, pcm, cfg.chunk_seconds)
        rows.append((cer(ref, hyp), ref, hyp, path.name, stats))

    rows.sort(key=lambda r: r[0], reverse=True)
    print("=== worst CER ===")
    for c, ref, hyp, name, stats in rows[: args.top]:
        print(
            f"CER={c:.3f} ref={ref!r} hyp={hyp!r} "
            f"silent={stats['chunks_silent']} empty={stats['chunks_empty']} ok={stats['chunks_ok']}"
        )

    cers = [r[0] for r in rows]
    exact = sum(1 for r in rows if normalize_text(r[1]) == normalize_text(r[2]))
    print("\n=== stats ===")
    print(f"n={len(rows)} mean_cer={statistics.mean(cers):.3f} median={statistics.median(cers):.3f}")
    print(f"exact={exact}/{len(rows)} ({exact/len(rows):.1%})")
    print(f"empty_hyp={sum(1 for r in rows if not normalize_text(r[2]))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
