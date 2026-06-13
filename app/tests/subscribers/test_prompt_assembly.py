from sub_llm.prompt_assembly import analyze_prompt_payload, build_ask_messages


def test_build_ask_messages_includes_game_reference_section() -> None:
    messages = build_ask_messages(
        "這遊戲好玩嗎",
        context="【直播狀態】",
        knowledge="知識片段",
        game_reference="【遊戲資料參考：Bad North】\n評分：媒體評分 80/100",
    )
    user = next(m["content"] for m in messages if m["role"] == "user")
    assert "遊戲資料參考：" in user
    assert "Bad North" in user
    assert "【回答方式】" in user
    assert user.index("知識庫參考：") < user.index("遊戲資料參考：") < user.index("觀眾問題：")


def test_analyze_prompt_payload_detects_game_reference_marker() -> None:
    analysis = analyze_prompt_payload(
        "評分",
        context="",
        game_reference="【遊戲資料參考：Demo】",
    )
    assert analysis["has_game_reference_marker"]
    assert analysis["game_reference_len"] > 0
