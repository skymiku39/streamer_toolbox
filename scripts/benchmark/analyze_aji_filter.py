"""分析語音 ground truth（檔名）被 hallucination filter 擋下的原因。

開發用一次性分析，不納入 CI。音檔目錄以 ``--audio-dir`` 指定。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from safety.stt_input import (
    _DEFAULT_BLOCKLIST,
    _FILLER_ONLY,
    _STRUCTURE_PATTERNS,
    _is_repetitive_hallucination,
    _matches_blocklist,
    _normalize_for_match,
    is_hallucination_text,
)


def why_blocked(text: str) -> list[str]:
    raw = _normalize_for_match(text)
    reasons: list[str] = []
    if not raw or len(raw) < 2:
        reasons.append("empty_or_1char")
    if _FILLER_ONLY.match(raw):
        reasons.append("filler_only")
    if _STRUCTURE_PATTERNS.search(raw):
        reasons.append("structure_pattern")
    if _is_repetitive_hallucination(text):
        reasons.append("repetitive")
    if _matches_blocklist(text, _DEFAULT_BLOCKLIST):
        reasons.append("blocklist")
    letters = sum(1 for char in raw if char.isalnum())
    if len(raw) <= 6 and letters <= 2:
        reasons.append("short_text_heuristic")
    return reasons


def classify_intent(text: str, reasons: list[str]) -> str:
    """對阿吉實際台詞而言，filter 是否合理。"""
    if "blocklist" in reasons or "structure_pattern" in reasons:
        return "合理過濾目標（若 Whisper 吐這些）"
    if reasons == ["filler_only"] or (
        "filler_only" in reasons and len(reasons) == 1
    ):
        return "邊界（語助詞，可能是真實台詞）"
    if "short_text_heuristic" in reasons:
        if text in {"呵呵", "然後", "喔↘️", "欸_", "呃", "啊"}:
            return "誤殺（真實短句／語助詞）"
        return "可能誤殺（兩字詞，阿吉確實有說）"
    return "其他"


def main() -> None:
    parser = argparse.ArgumentParser(description="分析檔名 ground truth 被 STT filter 擋下的原因")
    parser.add_argument("--audio-dir", required=True, help="含 mp3 的音檔目錄")
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    blocked_rows: list[tuple[str, list[str], str]] = []
    passed: list[str] = []

    for path in sorted(audio_dir.glob("*.mp3")):
        ref = path.stem.split("_", 2)[-1]
        if not ref or ref.startswith("("):
            continue
        if is_hallucination_text(ref):
            blocked_rows.append((ref, why_blocked(ref), path.name))
        else:
            passed.append(ref)

    by_ref: dict[str, dict] = {}
    for ref, reasons, fname in blocked_rows:
        entry = by_ref.setdefault(ref, {"reasons": reasons, "files": []})
        entry["files"].append(fname)

    print(f"通過: {len(passed)} 種文字")
    print(f"被擋: {len(blocked_rows)} 檔 / {len(by_ref)} 種\n")

    reasonable: list[str] = []
    borderline: list[str] = []
    false_positive: list[str] = []

    for ref in sorted(by_ref):
        reasons = by_ref[ref]["reasons"]
        intent = classify_intent(ref, reasons)
        count = len(by_ref[ref]["files"])
        print(f"  {ref!r:10} rules={reasons} x{count} -> {intent}")
        if "合理過濾" in intent:
            reasonable.append(ref)
        elif "邊界" in intent:
            borderline.append(ref)
        else:
            false_positive.append(ref)

    print("\n=== 摘要 ===")
    print(f"合理過濾目標（阿吉檔名中出現）: {reasonable or '（無）'}")
    print(f"邊界（語助詞）: {sorted(set(borderline))}")
    print(f"誤殺（阿吉真實台詞）: {sorted(set(false_positive))}")

    # 典型幻覺是否在阿吉檔名
    hints = ("subscribe", "thank", "訂閱", "收看", "字幕", "http", "music")
    classic_files = [
        p.name
        for p in audio_dir.glob("*.mp3")
        if any(h in p.stem.lower() for h in hints)
    ]
    print(f"\n阿吉檔名含典型幻覺關鍵字: {len(classic_files)} 個")


if __name__ == "__main__":
    main()
