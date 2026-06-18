from sub_llm.prompt_assembly import analyze_prompt_payload
from sub_llm.prompt_inspect import (
    AskInputs,
    InspectCase,
    _relevance_score,
    evaluate_inspect_cases,
    inspect_ask_prompt,
)


def test_relevance_score_counts_question_tokens_in_blobs() -> None:
    score = _relevance_score("LNG 是什麼", "LNG Live 是台灣實況團體")
    assert score > 0.3


def test_inspect_ask_prompt_flags_empty_context_warning() -> None:
    result = inspect_ask_prompt(
        "測試問題",
        channel="demo",
        inputs=AskInputs(
            context="",
            knowledge="",
            game_reference="",
            session_recap_reference="",
        ),
    )
    assert result.warnings
    assert result.score < 0.6


def test_inspect_ask_prompt_passes_with_knowledge() -> None:
    inputs = AskInputs(
        context="逐字稿:主播在測試",
        knowledge="知識:777 是幸運數字",
        game_reference="",
        session_recap_reference="",
    )
    result = inspect_ask_prompt("777 幸運數字", channel="demo", inputs=inputs)
    assert result.analysis["has_static_kb_marker"]
    assert result.analysis["has_stt_marker"]
    assert result.relevance > 0
    assert result.passed


def test_evaluate_inspect_cases_checks_fragments_and_layers() -> None:
    def inspect_fn(question: str, channel: str):
        del channel
        inputs = AskInputs(
            context="",
            knowledge="知識:LNG Live 台灣實況",
            game_reference="",
            session_recap_reference="",
        )
        return inspect_ask_prompt(question, channel="demo", inputs=inputs)

    cases = [
        InspectCase(
            question="誰是 LNG",
            expect=("LNG",),
            expect_layers=("static_kb",),
            any_of=True,
        )
    ]
    results = evaluate_inspect_cases(inspect_fn, cases)
    assert len(results) == 1
    assert results[0].passed
    assert results[0].found == ("LNG",)
    assert results[0].layer_missing == ()


def test_analyze_prompt_payload_still_available() -> None:
    analysis = analyze_prompt_payload("q", context="逐字稿:hello", knowledge="記憶:摘要")
    assert analysis["has_stt_marker"]
    assert analysis["has_memory_marker"]
