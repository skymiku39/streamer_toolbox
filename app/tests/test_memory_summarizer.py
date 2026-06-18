from __future__ import annotations

import json
from unittest.mock import patch

from app.workers.memory_summarizer import (
    LlmSummarizer,
    parse_both_response,
)
from stream_store.models import TextRecord


def _chat(ts: str, text: str) -> TextRecord:
    return TextRecord(
        id=0,
        session_id="s",
        source="chat",
        timestamp=ts,
        text=text,
        author="viewer",
        channel="demo",
        message_id="c",
    )


def _stt(ts: str, text: str) -> TextRecord:
    return TextRecord(
        id=0,
        session_id="s",
        source="stt",
        timestamp=ts,
        text=text,
        author="",
        channel="demo",
        message_id="s",
    )


def test_parse_both_response_valid() -> None:
    raw = json.dumps(
        {
            "chat": {"summary": "聊天熱絡", "category": "discussion"},
            "stt": {"summary": "打 Boss", "category": "progress"},
        },
        ensure_ascii=False,
    )
    parsed = parse_both_response(raw)
    assert parsed is not None
    chat_draft, stt_draft = parsed
    assert chat_draft.content == "聊天熱絡"
    assert chat_draft.category == "discussion"
    assert stt_draft.content == "打 Boss"
    assert stt_draft.category == "progress"


def test_parse_both_response_strips_code_fence() -> None:
    raw = '```json\n{"chat":{"summary":"a"},"stt":{"summary":"b"}}\n```'
    parsed = parse_both_response(raw)
    assert parsed is not None
    assert parsed[0].content == "a"
    assert parsed[1].content == "b"


def test_parse_both_response_missing_section_returns_none() -> None:
    raw = json.dumps({"chat": {"summary": "only chat"}})
    assert parse_both_response(raw) is None


def test_parse_both_response_invalid_json_returns_none() -> None:
    assert parse_both_response("not json") is None


def test_llm_summarizer_both_single_call_when_parsed() -> None:
    summarizer = LlmSummarizer(
        base_url="https://example/v1",
        api_key="k",
        model="gemini-2.5-flash",
    )
    merged = json.dumps(
        {
            "chat": {"summary": "聊天摘要", "category": "discussion"},
            "stt": {"summary": "語音摘要", "category": "progress"},
        },
        ensure_ascii=False,
    )
    with patch.object(LlmSummarizer, "_complete", return_value=merged) as complete:
        chat_draft, stt_draft = summarizer.summarize_both(
            [_chat("2026-06-12T10:00:00+00:00", "hi")],
            [_stt("2026-06-12T10:00:30+00:00", "yo")],
        )
    assert complete.call_count == 1
    assert chat_draft.content == "聊天摘要"
    assert stt_draft.content == "語音摘要"


def test_llm_summarizer_both_falls_back_to_separate_on_bad_json() -> None:
    summarizer = LlmSummarizer(
        base_url="https://example/v1",
        api_key="k",
        model="gemini-2.5-flash",
    )
    with patch.object(
        LlmSummarizer,
        "_complete",
        side_effect=["garbage merged", "聊天分開摘要", "語音分開摘要"],
    ) as complete:
        chat_draft, stt_draft = summarizer.summarize_both(
            [_chat("2026-06-12T10:00:00+00:00", "hi")],
            [_stt("2026-06-12T10:00:30+00:00", "yo")],
        )
    assert complete.call_count == 3
    assert chat_draft.content == "聊天分開摘要"
    assert stt_draft.content == "語音分開摘要"
