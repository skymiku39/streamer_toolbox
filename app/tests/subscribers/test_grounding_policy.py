from __future__ import annotations

import pytest

from sub_llm.grounding_policy import (
    grounding_client_enabled,
    resolve_web_search_mode,
    should_use_grounding,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("auto", "auto"),
        ("true", "on"),
        ("1", "on"),
        ("on", "on"),
        ("false", "off"),
        ("0", "off"),
        ("", "off"),
        ("garbage", "off"),
    ],
)
def test_resolve_web_search_mode(raw: str, expected: str) -> None:
    assert resolve_web_search_mode(raw) == expected


def test_grounding_client_enabled() -> None:
    assert grounding_client_enabled("on") is True
    assert grounding_client_enabled("auto") is True
    assert grounding_client_enabled("off") is False


def test_should_use_grounding_off_never_searches() -> None:
    used, reason = should_use_grounding("今天有什麼新聞", mode="off")
    assert used is False
    assert reason == "mode_off"


def test_should_use_grounding_on_always_searches() -> None:
    used, reason = should_use_grounding("你喜歡什麼顏色", mode="on")
    assert used is True
    assert reason == "mode_on"


def test_auto_triggers_on_realtime_keyword() -> None:
    used, reason = should_use_grounding("今天天氣如何", mode="auto")
    assert used is True
    assert reason == "realtime_keyword"


def test_auto_skips_when_covered_by_context() -> None:
    used, reason = should_use_grounding(
        "這個角色的背景故事是什麼",
        knowledge="角色設定：...",
        mode="auto",
    )
    assert used is False
    assert reason == "covered_by_context"


def test_auto_skips_when_no_signal() -> None:
    used, reason = should_use_grounding("你覺得呢", mode="auto")
    assert used is False
    assert reason == "no_signal"


def test_auto_reads_env_when_mode_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_WEB_SEARCH", "auto")
    used, reason = should_use_grounding("最新版本更新了嗎")
    assert used is True
    assert reason == "realtime_keyword"
