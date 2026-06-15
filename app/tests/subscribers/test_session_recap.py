from __future__ import annotations

from pathlib import Path

import pytest
from stream_store import StreamTextStore, set_active_session_for_channel

from sub_llm.live_activity import is_current_activity_question
from sub_llm.prompt_assembly import analyze_prompt_payload, build_ask_messages
from sub_llm.session_recap import (
    build_session_recap_reference,
    should_enrich_session_recap,
)


def test_should_enrich_session_recap_positive() -> None:
    assert should_enrich_session_recap("主播今天實現了哪些功能")
    assert should_enrich_session_recap("本場做了什麼")
    assert should_enrich_session_recap("開台以來進度如何")


def test_should_enrich_session_recap_negative() -> None:
    assert not should_enrich_session_recap("蒜頭王八是什麼")
    assert not should_enrich_session_recap("")
    assert not should_enrich_session_recap("主播剛剛在幹嘛")


def test_session_recap_excludes_current_activity_questions() -> None:
    question = "主播剛剛在幹嘛"
    assert is_current_activity_question(question)
    assert not should_enrich_session_recap(question)


def test_build_session_recap_reference_excludes_qa_summaries(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    session_id = "demo_20260614"
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-14T10:00:00+00:00",
        period_end="2026-06-14T10:30:00+00:00",
        source="qa",
        content="觀眾 問：做了什麼\nbot 答：Godot 自動化",
        record_count=1,
    )
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-14T10:30:00+00:00",
        period_end="2026-06-14T11:00:00+00:00",
        source="stt",
        content="- 實作 session_recap enrichment 模組",
        record_count=2,
    )
    store.append_stt(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-14T11:05:00+00:00",
        text="最新段落",
        segment_id="s-new",
    )
    set_active_session_for_channel(store, channel="demo", session_id=session_id)

    recap = build_session_recap_reference(
        "主播今天做了什麼",
        channel="demo",
        store=store,
    )
    assert recap.qa_summary_count == 1
    assert recap.summary_count == 1
    assert "Godot 自動化" not in recap.text
    assert "session_recap enrichment" in recap.text
    assert "最新段落" in recap.text
    store.close()


def test_build_session_recap_reference_includes_summaries_and_pending_stt(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    session_id = "demo_20260614"
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-14T10:00:00+00:00",
        period_end="2026-06-14T10:30:00+00:00",
        source="stt",
        content="- 實作 !ask 本場回顧 enrichment",
        record_count=3,
    )
    store.append_stt(
        session_id=session_id,
        channel="demo",
        timestamp="2026-06-14T10:35:00+00:00",
        text="接著要跑 pytest",
        segment_id="s1",
    )
    set_active_session_for_channel(store, channel="demo", session_id=session_id)

    recap = build_session_recap_reference(
        "主播今天做了什麼",
        channel="demo",
        store=store,
    )
    assert recap.summary_count == 1
    assert recap.raw_stt_count == 1
    assert "【本場回顧參考】" in recap.text
    assert "本場回顧 enrichment" in recap.text
    assert "接著要跑 pytest" in recap.text
    store.close()


def test_build_session_recap_reference_skips_general_questions(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    session_id = "demo_20260614"
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-14T10:00:00+00:00",
        period_end="2026-06-14T10:30:00+00:00",
        source="chat",
        content="聊天摘要",
        record_count=1,
    )
    set_active_session_for_channel(store, channel="demo", session_id=session_id)

    recap = build_session_recap_reference(
        "蒜頭王八是什麼",
        channel="demo",
        store=store,
    )
    assert recap.text == ""
    assert recap.summary_count == 0
    store.close()


def test_build_session_recap_reference_respects_max_chars(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_SESSION_RECAP_MAX_CHARS", "120")
    db_path = tmp_path / "stream.db"
    store = StreamTextStore(db_path)
    session_id = "demo_20260614"
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-14T10:00:00+00:00",
        period_end="2026-06-14T10:30:00+00:00",
        source="stt",
        content="X" * 200,
        record_count=1,
    )
    set_active_session_for_channel(store, channel="demo", session_id=session_id)

    recap = build_session_recap_reference(
        "今天做了什麼",
        channel="demo",
        store=store,
    )
    assert recap.text.endswith("...")
    assert len(recap.text) <= 120
    store.close()


def test_build_ask_messages_includes_session_recap_section() -> None:
    messages = build_ask_messages(
        "今天做了什麼",
        context="【直播狀態】",
        knowledge="知識片段",
        session_recap_reference="【本場回顧參考】\n- 實作 enrichment",
    )
    user = next(m["content"] for m in messages if m["role"] == "user")
    assert "本場回顧參考：" in user
    assert "實作 enrichment" in user
    assert user.index("知識庫參考：") < user.index("本場回顧參考：") < user.index("【回答方式】")


def test_analyze_prompt_payload_detects_session_recap_marker() -> None:
    analysis = analyze_prompt_payload(
        "今天進度",
        context="",
        session_recap_reference="【本場回顧參考】\n摘要",
    )
    assert analysis["has_session_recap_marker"]
    assert analysis["session_recap_len"] > 0
