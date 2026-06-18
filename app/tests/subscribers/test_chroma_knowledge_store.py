from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sub_llm.chroma_store import (
    ChromaKnowledgeStore,
    _fingerprint_documents,
    _lexical_chunk_matches,
    _usable_knowledge_chunks,
)
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
    mock_collection.count.return_value = 1
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
    mock_collection.count.return_value = 1
    mock_collection.query.return_value = {"documents": [["週五晚上八點"]]}
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    chromadb = MagicMock()
    chromadb.PersistentClient.return_value = mock_client
    monkeypatch.setitem(__import__("sys").modules, "chromadb", chromadb)

    store = ChromaKnowledgeStore(knowledge_dir, chroma_dir=chroma_dir)
    snippet = store.query("直播時間")

    assert "知識:" in snippet
    assert "週五晚上八點" in snippet


def test_usable_knowledge_chunks_keeps_lines_without_placeholders() -> None:
    raw = "常用梗與用語\n- 777：聊天室幸運數字\n- [請填寫頻道專屬梗]"
    usable = _usable_knowledge_chunks([raw])
    assert len(usable) == 1
    assert "777" in usable[0]
    assert "[請填寫" not in usable[0]


def test_lexical_chunk_matches_finds_numeric_slang(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "faq.md").write_text(
        "## 禁止事項\n不得洩漏 API key\n\n## 常用梗\n777：聊天室幸運數字",
        encoding="utf-8",
    )
    matches = _lexical_chunk_matches("777 是什麼意思", knowledge_dir, limit=2)
    assert matches
    assert "777" in matches[0]


def test_chroma_query_reranks_by_keyword_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "faq.md").write_text(
        "## 禁止事項\n不得洩漏 API key\n\n## 常用梗\n777：聊天室幸運數字",
        encoding="utf-8",
    )
    chroma_dir = tmp_path / "chroma"

    ban_doc = "禁止事項\n不得洩漏 API key"
    meme_doc = "常用梗\n777：聊天室幸運數字"
    mock_collection = MagicMock()
    mock_collection.count.return_value = 2
    mock_collection.query.return_value = {"documents": [[ban_doc, meme_doc]]}
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    chromadb = MagicMock()
    chromadb.PersistentClient.return_value = mock_client
    monkeypatch.setitem(__import__("sys").modules, "chromadb", chromadb)

    store = ChromaKnowledgeStore(knowledge_dir, chroma_dir=chroma_dir)
    snippet = store.query("777 是什麼意思")

    assert "777" in snippet
    assert snippet.split("·")[0].endswith("幸運數字") or "777" in snippet.split("·")[0]


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
