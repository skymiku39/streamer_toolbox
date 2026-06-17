from sub_llm.prompt_format import (
    build_user_prompt,
    filter_knowledge_for_prompt,
    is_placeholder_knowledge,
    join_groups,
    join_lines,
)
from sub_llm.prompt_assembly import analyze_prompt_payload, build_ask_messages


def test_build_user_prompt_separates_live_reference_and_question() -> None:
    user = build_user_prompt(
        "主播今天做了什麼？",
        context="狀態:直播中·澄天芽\n逐字稿:剛剛在煉藥",
        knowledge="知識:777 是幸運數字",
        game_reference="遊戲:Potion Craft·媒體70",
        session_recap_reference="回顧摘要:stt:打了 Boss",
    )
    assert user.index("[直播]") < user.index("[參考]") < user.index("[問題]")
    assert "【回答】" not in user
    assert "【輸出格式】" not in user
    assert "逐字稿:" in user
    assert "遊戲:Potion Craft" in user


def test_filter_knowledge_for_prompt_drops_placeholders() -> None:
    raw = (
        "知識:VIP 與常駐觀眾 [請填寫暱稱]·禁止事項 不得洩漏 API key"
        "·回覆風格 簡短友善"
    )
    filtered = filter_knowledge_for_prompt(raw)
    assert "[請填寫" not in filtered
    assert "回覆風格" in filtered


def test_build_ask_messages_puts_rules_in_system() -> None:
    messages = build_ask_messages(
        "這遊戲好玩嗎",
        context="狀態:直播中",
        knowledge="知識:知識片段",
        game_reference="遊戲:Bad North·媒體80",
        session_recap_reference="回顧摘要:stt:進度",
    )
    system = next(m["content"] for m in messages if m["role"] == "system")
    user = next(m["content"] for m in messages if m["role"] == "user")
    assert "【回答】" in system
    assert "【本場回顧】" in system
    assert "【回答】" not in user
    assert "[問題]" in user
    assert user.index("[參考]") < user.index("[問題]")


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
    assert user.index("知識:") < user.index("遊戲:")


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
        session_recap_reference="回顧摘要:stt:摘要",
    )
    user = next(m["content"] for m in messages if m["role"] == "user")
    assert user.index("遊戲:") < user.index("回顧摘要:")
