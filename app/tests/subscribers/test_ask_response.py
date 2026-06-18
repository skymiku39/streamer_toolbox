import json

from sub_llm.ask_response import AskResponse, parse_ask_response, parse_plain_llm_text
from sub_llm.qa_memory_gate import should_persist_qa_memory


def test_parse_ask_response_from_json() -> None:
    raw = json.dumps(
        {
            "reply": "這是回覆",
            "store_worthy": True,
            "memory_value": 4,
            "memory_note": "精簡記憶",
            "category": "progress",
        },
        ensure_ascii=False,
    )
    parsed = parse_ask_response(raw)
    assert parsed == AskResponse(
        reply="這是回覆",
        store_worthy=True,
        memory_value=4,
        memory_note="精簡記憶",
        category="progress",
    )


def test_parse_ask_response_missing_category_defaults_to_low_trust() -> None:
    # 未分類時正規化為最低可信度 discussion，避免被當事實。
    raw = json.dumps(
        {
            "reply": "這是回覆",
            "store_worthy": True,
            "memory_value": 4,
            "memory_note": "精簡記憶",
        },
        ensure_ascii=False,
    )
    assert parse_ask_response(raw).category == "discussion"


def test_parse_ask_response_unknown_category_falls_back() -> None:
    raw = json.dumps(
        {"reply": "嗨", "category": "not_a_real_category"},
        ensure_ascii=False,
    )
    assert parse_ask_response(raw).category == "discussion"


def test_parse_ask_response_plain_text_fallback() -> None:
    assert parse_ask_response("純文字回覆").reply == "純文字回覆"


def test_parse_ask_response_accepts_message_key() -> None:
    raw = json.dumps({"message": "哈囉！"}, ensure_ascii=False)
    assert parse_ask_response(raw).reply == "哈囉！"


def test_parse_plain_llm_text_extracts_message_key() -> None:
    raw = json.dumps({"message": "啟動招呼"}, ensure_ascii=False)
    assert parse_plain_llm_text(raw) == "啟動招呼"


def test_parse_plain_llm_text_returns_plain_text() -> None:
    assert parse_plain_llm_text("直接輸出") == "直接輸出"


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
