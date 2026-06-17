from __future__ import annotations

import pytest

from sub_llm.llm_backends import (
    BACKEND_GEMINI,
    BACKEND_HYBRID,
    argparse_backend_help,
    format_backend_log_tag,
    is_gemini_direct_backend,
    is_hybrid_agent_backend,
    normalize_backend_id,
    resolve_backend_info,
    resolve_backend_label,
)


def test_gemini_direct_naming() -> None:
    info = resolve_backend_info(BACKEND_GEMINI)
    assert info.display_name == "Gemini 直連"
    assert info.slug == "gemini-direct"
    assert is_gemini_direct_backend(BACKEND_GEMINI)
    assert not is_hybrid_agent_backend(BACKEND_GEMINI)


def test_hybrid_agent_naming() -> None:
    info = resolve_backend_info(BACKEND_HYBRID)
    assert info.display_name == "Hybrid Agent"
    assert info.slug == "hybrid-agent"
    assert is_hybrid_agent_backend(BACKEND_HYBRID)
    assert not is_gemini_direct_backend(BACKEND_HYBRID)


def test_resolve_backend_label_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "hybrid")
    assert resolve_backend_label() == "Hybrid Agent"
    assert normalize_backend_id() == "hybrid"


def test_format_backend_log_tag() -> None:
    tag = format_backend_log_tag(BACKEND_HYBRID)
    assert "Hybrid Agent" in tag
    assert "hybrid-agent" in tag


def test_argparse_backend_help_lists_all_backends() -> None:
    help_text = argparse_backend_help()
    assert "Gemini 直連" in help_text
    assert "Hybrid Agent" in help_text
    assert "gemini" in help_text
    assert "hybrid" in help_text
