from __future__ import annotations

from sub_llm.ask_flow_guard import ALLOW, CACHED, CANNED, AskFlowGuard


def _guard(now=None) -> AskFlowGuard:
    return AskFlowGuard(
        window_seconds=120,
        canned_reply="soft",
        hard_canned_reply="hard",
        now=now,
    )


def test_first_ask_is_allowed() -> None:
    decision = _guard().check("demo", "今天玩什麼")
    assert decision.action == ALLOW
    assert decision.should_call_llm


def test_second_ask_returns_cached_when_recorded() -> None:
    guard = _guard()
    guard.check("demo", "問題")
    guard.record_reply("demo", "問題", "答案")
    decision = guard.check("demo", "問題")
    assert decision.action == CACHED
    assert decision.reply == "答案"
    assert not decision.should_call_llm


def test_second_ask_without_cache_returns_soft_canned() -> None:
    guard = _guard()
    guard.check("demo", "問題")
    decision = guard.check("demo", "問題")
    assert decision.action == CANNED
    assert decision.reply == "soft"


def test_third_ask_returns_hard_canned() -> None:
    guard = _guard()
    guard.check("demo", "問題")
    guard.check("demo", "問題")
    decision = guard.check("demo", "問題")
    assert decision.action == CANNED
    assert decision.reply == "hard"


def test_window_expiry_resets_to_allow() -> None:
    clock = {"t": 1000.0}
    guard = _guard(now=lambda: clock["t"])
    assert guard.check("demo", "問題").action == ALLOW
    clock["t"] += 121
    assert guard.check("demo", "問題").action == ALLOW


def test_key_normalizes_channel_and_question() -> None:
    guard = _guard()
    guard.check("#Demo", "問題 ")
    guard.record_reply("demo", "問題", "答案")
    decision = guard.check("demo", "問題")
    assert decision.action == CACHED
    assert decision.reply == "答案"


def test_different_questions_are_independent() -> None:
    guard = _guard()
    guard.check("demo", "問題甲")
    decision = guard.check("demo", "問題乙")
    assert decision.action == ALLOW
