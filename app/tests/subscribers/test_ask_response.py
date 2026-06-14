import json

from sub_llm.ask_response import AskResponse, parse_ask_response
from sub_llm.qa_memory_gate import should_persist_qa_memory


def test_parse_ask_response_from_json() -> None:
    raw = json.dumps(
        {
            "reply": "這是回覆",
            "store_worthy": True,
            "memory_value": 4,
            "memory_note": "精簡記憶",
        },
        ensure_ascii=False,
    )
    parsed = parse_ask_response(raw)
    assert parsed == AskResponse(
        reply="這是回覆",
        store_worthy=True,
        memory_value=4,
        memory_note="精簡記憶",
    )


def test_parse_ask_response_plain_text_fallback() -> None:
    assert parse_ask_response("純文字回覆").reply == "純文字回覆"


def test_should_persist_qa_memory_rejects_low_value_reply() -> None:
    response = AskResponse(
        reply="直播中沒提到",
        store_worthy=True,
        memory_value=5,
        memory_note="某記憶",
    )
    assert not should_persist_qa_memory(
        response,
        question="測試問題",
        published_reply="直播中沒提到",
        min_memory_value=3,
    )


def test_should_persist_qa_memory_accepts_good_response() -> None:
    response = AskResponse(
        reply="我們在玩 DND 第五版",
        store_worthy=True,
        memory_value=4,
        memory_note="觀眾問目前在玩什麼，bot 答 DND 第五版。",
    )
    assert should_persist_qa_memory(
        response,
        question="現在在玩什麼",
        published_reply="我們在玩 DND 第五版",
        min_memory_value=3,
    )
