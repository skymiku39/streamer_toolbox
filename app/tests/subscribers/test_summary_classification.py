from __future__ import annotations

from app.workers.memory_summarizer import SummaryDraft, parse_summary_response


def test_parse_json_with_valid_category() -> None:
    draft = parse_summary_response('{"summary":"今天打了 Boss","category":"progress"}')
    assert draft == SummaryDraft(content="今天打了 Boss", category="progress")


def test_parse_json_invalid_category_falls_back_to_default() -> None:
    draft = parse_summary_response('{"summary":"閒聊","category":"weird"}')
    assert draft.content == "閒聊"
    assert draft.category == "discussion"


def test_parse_json_missing_category_keeps_empty() -> None:
    draft = parse_summary_response('{"summary":"只有摘要"}')
    assert draft.content == "只有摘要"
    assert draft.category == ""


def test_parse_code_fenced_json() -> None:
    draft = parse_summary_response('```json\n{"summary":"設備說明","category":"fact"}\n```')
    assert draft.content == "設備說明"
    assert draft.category == "fact"


def test_parse_plain_text_without_json() -> None:
    draft = parse_summary_response("這是一段純文字摘要")
    assert draft.content == "這是一段純文字摘要"
    assert draft.category == ""
