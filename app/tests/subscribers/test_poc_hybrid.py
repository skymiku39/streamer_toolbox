from __future__ import annotations

import os

import pytest

from sub_llm.poc_hybrid import (
    apply_hybrid_poc_env_defaults,
    hybrid_poc_feature_flags,
)


@pytest.fixture
def clean_hybrid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "LLM_GAME_INFO_ENABLED",
        "LLM_SESSION_RECAP_ENABLED",
        "LLM_MEMORY_FROM_DB",
        "LLM_SHORT_TERM_RAG_ENABLED",
        "LLM_INJECTION_GUARD",
        "LLM_KNOWLEDGE_BACKEND",
        "LLM_WEB_SEARCH",
        "LLM_STARTUP_ANNOUNCEMENT",
        "QA_MEMORY_MODE",
        "LLM_KNOWLEDGE_PATH",
    ):
        monkeypatch.delenv(key, raising=False)


def test_apply_hybrid_defaults_enables_zero_token_features(
    clean_hybrid_env: None,
) -> None:
    applied = apply_hybrid_poc_env_defaults(knowledge_path="/data/knowledge")

    assert "LLM_GAME_INFO_ENABLED" in applied
    assert "LLM_MEMORY_FROM_DB" in applied
    assert os.environ["LLM_GAME_INFO_ENABLED"] == "true"
    assert os.environ["LLM_MEMORY_FROM_DB"] == "true"
    assert os.environ["LLM_KNOWLEDGE_PATH"] == "/data/knowledge"


def test_apply_hybrid_defaults_disables_token_consumers(
    clean_hybrid_env: None,
) -> None:
    apply_hybrid_poc_env_defaults()

    assert os.environ["LLM_WEB_SEARCH"] == "false"
    assert os.environ["LLM_STARTUP_ANNOUNCEMENT"] == "false"
    assert os.environ["QA_MEMORY_MODE"] == "none"


def test_apply_hybrid_defaults_does_not_override_existing_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_MEMORY_FROM_DB", "false")
    monkeypatch.setenv("LLM_WEB_SEARCH", "true")

    applied = apply_hybrid_poc_env_defaults()

    assert "LLM_MEMORY_FROM_DB" not in applied
    assert "LLM_WEB_SEARCH" not in applied
    assert os.environ["LLM_MEMORY_FROM_DB"] == "false"
    assert os.environ["LLM_WEB_SEARCH"] == "true"


def test_hybrid_poc_feature_flags_reflects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_GAME_INFO_ENABLED", "true")
    monkeypatch.setenv("LLM_MEMORY_FROM_DB", "true")
    monkeypatch.setenv("LLM_KNOWLEDGE_PATH", "data/knowledge")
    monkeypatch.setenv("LLM_WEB_SEARCH", "false")

    flags = hybrid_poc_feature_flags()

    assert flags["game_info"] is True
    assert flags["l2_memory_rag"] is True
    assert flags["static_kb"] is True
    assert flags["web_search"] is False
