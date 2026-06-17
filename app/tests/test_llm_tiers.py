import pytest

from app.llm_tiers import (
    LlmTier,
    format_sub_llm_tier_log,
    resolve_tier,
)
from app.workers.memory_summarizer import LlmSummarizer


def test_ask_tier_prefers_llm_ask_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "gemini")
    monkeypatch.setenv("LLM_ASK_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.0-flash")
    tier = resolve_tier(LlmTier.ASK, ask_backend="gemini")
    assert tier.model == "gemini-2.5-flash"


def test_ask_tier_falls_back_to_llm_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "gemini")
    monkeypatch.delenv("LLM_ASK_MODEL", raising=False)
    monkeypatch.setenv("GOOGLE_AI_MODEL", "gemini-2.5-flash")
    tier = resolve_tier(LlmTier.ASK, ask_backend="gemini")
    assert tier.model == "gemini-2.5-flash"


def test_memory_tier_defaults_to_pro_for_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_LLM_BACKEND", "gemini")
    monkeypatch.delenv("MEMORY_LLM_MODEL", raising=False)
    monkeypatch.delenv("GOOGLE_AI_MEMORY_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    tier = resolve_tier(LlmTier.MEMORY, memory_backend="gemini")
    assert tier.model == "gemini-2.5-pro"


def test_memory_tier_uses_dedicated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_LLM_BACKEND", "gemini")
    monkeypatch.setenv("MEMORY_LLM_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")
    tier = resolve_tier(LlmTier.MEMORY, memory_backend="gemini")
    assert tier.model == "gemini-2.5-pro"


def test_memory_summarizer_ignores_ask_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_LLM_BACKEND", "gemini")
    monkeypatch.setenv("MEMORY_LLM_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "test-key")
    summarizer = LlmSummarizer.from_env(memory_backend="gemini")
    assert summarizer._model == "gemini-2.5-pro"


def test_hybrid_tier_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_AGENT_MODEL", "gemini-2.0-flash-lite")
    monkeypatch.setenv("LLM_ASK_MODEL", "gemini-2.5-flash")
    log = format_sub_llm_tier_log(ask_backend="hybrid")
    assert "agent=gemini-2.0-flash-lite" in log
    assert "ask=gemini-2.5-flash" in log
