from sub_llm.prompt_assembly import analyze_prompt_payload, build_ask_messages


def test_build_ask_messages_includes_all_sections() -> None:
    messages = build_ask_messages(
        "誰是 LNG",
        context="【近期聊天室（skymiku39）】\nviewer: LNG Live",
        knowledge="【實況主知識庫】\n777：幸運數字\n\n【近期直播摘要】\n[chat] 摘要",
        system_prompt="測試系統",
    )
    user = next(m["content"] for m in messages if m["role"] == "user")
    assert "近期直播上下文" in user
    assert "知識庫參考" in user
    assert "觀眾問題：誰是 LNG" in user
    assert "LNG Live" in user
    assert "【實況主知識庫】" in user
    assert "【近期直播摘要】" in user


def test_analyze_prompt_payload_detects_markers() -> None:
    analysis = analyze_prompt_payload(
        "主播在玩什麼",
        context="【直播逐字稿（skymiku39，最近片段）】\n[120s] 測試\n\n【近期聊天室（skymiku39）】\nviewer: hi",
        knowledge="【實況主知識庫】\n梗\n\n【近期直播摘要】\n[stt] 摘要",
        system_prompt="可用本身的常識",
    )
    assert analysis["has_stt_marker"] is True
    assert analysis["has_chat_marker"] is True
    assert analysis["has_static_kb_marker"] is True
    assert analysis["has_memory_marker"] is True
    assert analysis["has_general_knowledge_hint"] is True
