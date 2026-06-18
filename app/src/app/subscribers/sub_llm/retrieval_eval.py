"""記憶／知識檢索評測核心邏輯。

以固定問題集（每題標註期望出現的關鍵片段）量測檢索品質：

- 命中（hit）：期望片段是否出現在檢索結果文字中（大小寫不敏感）。
- recall@K：每題 = 命中片段數 / 期望片段數，再對所有題目取平均。
- pass：依 ``any_of`` 決定「全部命中」或「命中任一」。

純邏輯與資料 I/O 分離，並以可注入的 ``QueryFn`` 解耦實際檢索後端，
便於單元測試（傳入假 query_fn）與正式評測（傳入 Chroma 知識庫）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# (question, channel) -> 檢索結果文字（知識庫 query 的輸出）。
QueryFn = Callable[[str, str], str]


@dataclass(frozen=True)
class EvalCase:
    question: str
    expect: tuple[str, ...]
    channel: str = ""
    # True：命中任一期望片段即算通過；False：需全部命中。
    any_of: bool = False


@dataclass(frozen=True)
class CaseResult:
    case: EvalCase
    snippet: str
    found: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def recall(self) -> float:
        total = len(self.case.expect)
        if total == 0:
            return 1.0
        return len(self.found) / total

    @property
    def passed(self) -> bool:
        if not self.case.expect:
            return True
        if self.case.any_of:
            return bool(self.found)
        return not self.missing


@dataclass(frozen=True)
class EvalReport:
    results: tuple[CaseResult, ...]

    @property
    def recall_at_k(self) -> float:
        if not self.results:
            return 1.0
        return sum(result.recall for result in self.results) / len(self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 1.0
        return sum(1 for result in self.results if result.passed) / len(self.results)


def evaluate_cases(query_fn: QueryFn, cases: list[EvalCase]) -> EvalReport:
    results: list[CaseResult] = []
    for case in cases:
        snippet = query_fn(case.question, case.channel) or ""
        haystack = snippet.casefold()
        found = tuple(piece for piece in case.expect if piece.casefold() in haystack)
        missing = tuple(piece for piece in case.expect if piece.casefold() not in haystack)
        results.append(CaseResult(case=case, snippet=snippet, found=found, missing=missing))
    return EvalReport(results=tuple(results))


def load_cases(path: str | Path) -> list[EvalCase]:
    """讀取 JSON 問題集；每筆需含 question 與 expect（字串陣列）。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("評測資料集必須是 JSON 陣列")
    cases: list[EvalCase] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 筆評測案例必須是物件")
        question = str(item.get("question", "")).strip()
        if not question:
            raise ValueError(f"第 {index} 筆評測案例缺少 question")
        expect = tuple(str(piece) for piece in (item.get("expect") or []))
        cases.append(
            EvalCase(
                question=question,
                expect=expect,
                channel=str(item.get("channel", "")),
                any_of=bool(item.get("any_of", False)),
            )
        )
    return cases


def format_report(report: EvalReport) -> str:
    lines: list[str] = []
    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(
            f"[{status}] recall={result.recall:.2f} channel={result.case.channel!r} "
            f"q={result.case.question!r}"
        )
        if result.missing:
            lines.append(f"        missing={list(result.missing)}")
    lines.append(
        f"-- recall@K={report.recall_at_k:.3f} pass_rate={report.pass_rate:.3f} "
        f"({len(report.results)} cases)"
    )
    return "\n".join(lines)
