from sub_llm.prompt_assembly import analyze_prompt_payload, build_ask_messages


def test_build_ask_messages_includes_game_reference_section() -> None:
    messages = build_ask_messages(
        "這遊戲好玩嗎",
        context="狀態:直播中",
        knowledge="知識:知識片段",
        game_reference="遊戲:Bad North·媒體80",
    )
    user = next(m["content"] for m in messages if m["role"] == "user")
    assert "遊戲:" in user
    assert "Bad North" in user
    assert "【回答】" in user
    assert user.index("知識:") < user.index("遊戲:") < user.index("問題:")


def test_analyze_prompt_payload_detects_game_reference_marker() -> None:
    analysis = analyze_prompt_payload(
        "評分",
        context="",
        game_reference="遊戲:Demo",
    )
    assert analysis["has_game_reference_marker"]
    assert analysis["game_reference_len"] > 0


def test_build_ask_messages_orders_session_recap_after_game_reference() -> None:
    messages = build_ask_messages(
        "今天做了什麼",
        context="",
        game_reference="遊戲:Demo",
        session_recap_reference="回顧:摘要",
    )
    user = next(m["content"] for m in messages if m["role"] == "user")
    assert user.index("遊戲:") < user.index("回顧:")
