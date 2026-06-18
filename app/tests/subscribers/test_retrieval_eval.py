from __future__ import annotations

import json
from pathlib import Path

import pytest

from sub_llm.retrieval_eval import (
    EvalCase,
    evaluate_cases,
    format_report,
    load_cases,
)


def _query_fn(responses: dict[str, str]):
    def query_fn(question: str, channel: str) -> str:
        return responses.get(question, "")

    return query_fn


def test_recall_full_hit() -> None:
    cases = [EvalCase(question="麥克風?", expect=("SM7B", "Shure"))]
    report = evaluate_cases(_query_fn({"麥克風?": "記憶:主播用 Shure SM7B"}), cases)
    assert report.results[0].recall == 1.0
    assert report.results[0].passed
    assert report.recall_at_k == 1.0
    assert report.pass_rate == 1.0


def test_recall_partial_hit_fails_when_all_required() -> None:
    cases = [EvalCase(question="麥克風?", expect=("SM7B", "Shure"))]
    report = evaluate_cases(_query_fn({"麥克風?": "記憶:主播用 SM7B"}), cases)
    result = report.results[0]
    assert result.recall == 0.5
    assert result.found == ("SM7B",)
    assert result.missing == ("Shure",)
    assert not result.passed


def test_any_of_passes_on_single_hit() -> None:
    cases = [EvalCase(question="麥克風?", expect=("SM7B", "Shure"), any_of=True)]
    report = evaluate_cases(_query_fn({"麥克風?": "記憶:主播用 SM7B"}), cases)
    assert report.results[0].passed
    assert report.results[0].recall == 0.5


def test_case_insensitive_match() -> None:
    cases = [EvalCase(question="麥克風?", expect=("sm7b",))]
    report = evaluate_cases(_query_fn({"麥克風?": "記憶:SM7B"}), cases)
    assert report.results[0].passed


def test_empty_snippet_misses_all() -> None:
    cases = [EvalCase(question="x", expect=("a",))]
    report = evaluate_cases(_query_fn({}), cases)
    assert report.results[0].recall == 0.0
    assert not report.results[0].passed


def test_aggregate_metrics() -> None:
    cases = [
        EvalCase(question="a", expect=("x",)),
        EvalCase(question="b", expect=("y",)),
    ]
    report = evaluate_cases(_query_fn({"a": "x", "b": "no"}), cases)
    assert report.recall_at_k == 0.5
    assert report.pass_rate == 0.5


def test_load_cases_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            [{"question": "q1", "expect": ["a", "b"], "channel": "demo", "any_of": True}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    cases = load_cases(path)
    assert cases == [EvalCase(question="q1", expect=("a", "b"), channel="demo", any_of=True)]


def test_load_cases_rejects_missing_question(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{"expect": ["a"]}]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(path)


def test_format_report_marks_pass_and_fail() -> None:
    cases = [
        EvalCase(question="a", expect=("x",)),
        EvalCase(question="b", expect=("y",)),
    ]
    report = evaluate_cases(_query_fn({"a": "x"}), cases)
    text = format_report(report)
    assert "PASS" in text
    assert "FAIL" in text
    assert "recall@K" in text
