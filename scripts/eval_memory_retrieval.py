"""記憶／知識檢索評測 CLI。

以固定問題集對實際 Chroma 知識庫跑 recall@K，方便在調整 embedding、
排序權重、同步視窗後快速回歸驗證「記憶有沒有被正確召回」。

用法：
    uv run python scripts/eval_memory_retrieval.py \
        --cases scripts/eval/memory_retrieval_cases.json \
        --min-recall 0.6

未指定 --cases 時使用內建範例集；請依自己的頻道與記憶內容編輯該檔。
設定 --min-recall 後，recall@K 低於門檻會以非零碼結束（可用於 CI）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in ("app/src", "app/src/app/subscribers"):
    candidate = ROOT / rel
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from sub_llm.factory import (  # noqa: E402
    create_knowledge_store,
    preload_knowledge_store,
)
from sub_llm.retrieval_eval import (  # noqa: E402
    QueryFn,
    evaluate_cases,
    format_report,
    load_cases,
)

DEFAULT_CASES = ROOT / "scripts" / "eval" / "memory_retrieval_cases.json"


def _build_query_fn() -> QueryFn:
    store = create_knowledge_store()
    preload_knowledge_store(store)

    def query_fn(question: str, channel: str) -> str:
        return store.query(question, channel=channel)

    return query_fn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="記憶／知識檢索 recall@K 評測")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="評測問題集 JSON 路徑")
    parser.add_argument(
        "--min-recall",
        type=float,
        default=None,
        help="recall@K 門檻；低於此值則以非零碼結束（供 CI 使用）",
    )
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    if not cases:
        print("評測問題集為空，請先編輯案例。", file=sys.stderr)
        return 2

    report = evaluate_cases(_build_query_fn(), cases)
    print(format_report(report))

    if args.min_recall is not None and report.recall_at_k < args.min_recall:
        print(
            f"recall@K {report.recall_at_k:.3f} 低於門檻 {args.min_recall:.3f}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
