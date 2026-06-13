from __future__ import annotations

from pathlib import Path

import pytest

from sub_llm.chroma_store import ChromaKnowledgeStore, ChromaSummaryKnowledgeStore
from sub_llm.factory import create_knowledge_store, create_llm_client
from sub_llm.knowledge import (
    CompositeKnowledgeStore,
    EmptyKnowledgeStore,
    FileKnowledgeStore,
    SummaryKnowledgeStore,
)
from sub_llm.llm import TemplateLlmClient
from sub_llm.openai_client import OpenAiCompatibleLlmClient


def test_create_llm_client_template() -> None:
    client = create_llm_client("template")
    assert isinstance(client, TemplateLlmClient)


def test_create_llm_client_openai_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "key")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    client = create_llm_client("openai")
    assert isinstance(client, OpenAiCompatibleLlmClient)


def test_create_llm_client_gemini_uses_google_ai_env(monkeypatch) -> None:
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "google-key")
    monkeypatch.setenv("GOOGLE_AI_MODEL", "gemini-2.5-flash")
    client = create_llm_client("gemini")
    assert isinstance(client, OpenAiCompatibleLlmClient)
    assert client._model == "gemini-2.5-flash"
    assert client._api_key == "google-key"


def test_create_knowledge_store_db_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STREAM_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LLM_MEMORY_FROM_DB", "true")
    monkeypatch.delenv("LLM_KNOWLEDGE_PATH", raising=False)
    store = create_knowledge_store()
    assert isinstance(store, SummaryKnowledgeStore)


def test_create_knowledge_store_file_only(monkeypatch, tmp_path: Path) -> None:
    knowledge_file = tmp_path / "notes.txt"
    knowledge_file.write_text("manual knowledge", encoding="utf-8")
    monkeypatch.setenv("LLM_MEMORY_FROM_DB", "false")
    store = create_knowledge_store(str(knowledge_file))
    assert isinstance(store, FileKnowledgeStore)
    assert "manual knowledge" in store.query("manual")


def test_create_knowledge_store_composite_chroma_order(monkeypatch, tmp_path: Path) -> None:
    knowledge_file = tmp_path / "notes.txt"
    knowledge_file.write_text("file note", encoding="utf-8")
    monkeypatch.setenv("STREAM_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LLM_MEMORY_FROM_DB", "true")
    monkeypatch.setenv("LLM_KNOWLEDGE_BACKEND", "chroma")
    monkeypatch.setenv("LLM_CHROMA_DIR", str(tmp_path / "chroma"))
    store = create_knowledge_store(str(knowledge_file))
    assert isinstance(store, CompositeKnowledgeStore)
    child_types = [type(child).__name__ for child in store._stores]
    assert child_types == ["ChromaKnowledgeStore", "ChromaSummaryKnowledgeStore"]


def test_create_knowledge_store_empty_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MEMORY_FROM_DB", "false")
    monkeypatch.delenv("LLM_KNOWLEDGE_PATH", raising=False)
    store = create_knowledge_store()
    assert isinstance(store, EmptyKnowledgeStore)


def test_create_knowledge_store_rejects_unknown_backend(monkeypatch, tmp_path: Path) -> None:
    knowledge_file = tmp_path / "notes.txt"
    knowledge_file.write_text("x", encoding="utf-8")
    monkeypatch.setenv("LLM_MEMORY_FROM_DB", "false")
    monkeypatch.setenv("LLM_KNOWLEDGE_BACKEND", "unknown")
    with pytest.raises(ValueError, match="LLM_KNOWLEDGE_BACKEND"):
        create_knowledge_store(str(knowledge_file))
