from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sub_llm.chroma_store import ChromaKnowledgeStore, _fingerprint_documents
from sub_llm.factory import create_knowledge_store, preload_knowledge_store
from sub_llm.knowledge import CompositeKnowledgeStore


def test_fingerprint_documents_changes_when_content_changes() -> None:
    first = _fingerprint_documents([("a.md", "hello")])
    second = _fingerprint_documents([("a.md", "hello world")])
    assert first != second


def test_chroma_preload_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "faq.md").write_text("## 直播時間\n週五晚上八點", encoding="utf-8")
    chroma_dir = tmp_path / "chroma"

    mock_collection = MagicMock()
    mock_collection.query.return_value = {"documents": [["週五晚上八點"]]}
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection

    chromadb = MagicMock()
    chromadb.PersistentClient.return_value = mock_client
    monkeypatch.setitem(__import__("sys").modules, "chromadb", chromadb)

    store = ChromaKnowledgeStore(knowledge_dir, chroma_dir=chroma_dir)
    store.preload()
    store.preload()

    mock_collection.upsert.assert_called_once()
    assert chromadb.PersistentClient.call_count == 1


def test_chroma_skips_upsert_when_fingerprint_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "faq.md").write_text("固定內容", encoding="utf-8")
    chroma_dir = tmp_path / "chroma"

    mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    chromadb = MagicMock()
    chromadb.PersistentClient.return_value = mock_client
    monkeypatch.setitem(__import__("sys").modules, "chromadb", chromadb)

    store = ChromaKnowledgeStore(knowledge_dir, chroma_dir=chroma_dir)
    store.preload()
    store.preload()

    mock_collection.upsert.assert_called_once()


def test_chroma_query_returns_formatted_snippet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "faq.md").write_text("內容", encoding="utf-8")
    chroma_dir = tmp_path / "chroma"

    mock_collection = MagicMock()
    mock_collection.query.return_value = {"documents": [["週五晚上八點"]]}
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    chromadb = MagicMock()
    chromadb.PersistentClient.return_value = mock_client
    monkeypatch.setitem(__import__("sys").modules, "chromadb", chromadb)

    store = ChromaKnowledgeStore(knowledge_dir, chroma_dir=chroma_dir)
    snippet = store.query("直播時間")

    assert "【實況主知識庫】" in snippet
    assert "週五晚上八點" in snippet


def test_create_knowledge_store_chroma_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    knowledge_file = tmp_path / "notes.md"
    knowledge_file.write_text("chroma note", encoding="utf-8")
    monkeypatch.setenv("LLM_MEMORY_FROM_DB", "false")
    monkeypatch.setenv("LLM_KNOWLEDGE_BACKEND", "chroma")
    monkeypatch.setenv("LLM_CHROMA_DIR", str(tmp_path / "chroma"))

    store = create_knowledge_store(str(knowledge_file))
    assert isinstance(store, ChromaKnowledgeStore)


def test_preload_knowledge_store_calls_composite_children(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    knowledge_file = tmp_path / "notes.md"
    knowledge_file.write_text("note", encoding="utf-8")
    monkeypatch.setenv("STREAM_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LLM_MEMORY_FROM_DB", "true")
    monkeypatch.setenv("LLM_KNOWLEDGE_BACKEND", "chroma")
    monkeypatch.setenv("LLM_CHROMA_DIR", str(tmp_path / "chroma"))

    mock_collection = MagicMock()
    mock_collection.query.return_value = {"documents": [[]]}
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    chromadb = MagicMock()
    chromadb.PersistentClient.return_value = mock_client
    monkeypatch.setitem(__import__("sys").modules, "chromadb", chromadb)

    store = create_knowledge_store(str(knowledge_file))
    assert isinstance(store, CompositeKnowledgeStore)
    preload_knowledge_store(store)
    preload_knowledge_store(store)

    mock_collection.upsert.assert_called_once()
