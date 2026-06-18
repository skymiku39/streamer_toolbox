from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from stream_store import StreamTextStore, set_active_session_for_channel
from sub_llm.chroma_store import ChromaSummaryKnowledgeStore


def _setup_store_with_qa_and_chat(tmp_path: Path) -> StreamTextStore:
    store = StreamTextStore(tmp_path / "test.db")
    store.save_summary(
        session_id="room_a_20260612",
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="觀眾在問 777 梗",
        record_count=1,
    )
    store.save_summary(
        session_id="room_a_20260612",
        period_start="2026-06-12T10:10:00+00:00",
        period_end="2026-06-12T10:11:00+00:00",
        source="qa",
        content="alice 問：蒜頭王八\n觀眾問寶可夢諧音梗",
        record_count=1,
    )
    set_active_session_for_channel(store, channel="room_a", session_id="room_a_20260612")
    return store


def _mock_chroma(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    qa_doc = "[qa] 2026-06-12T10:10:00+00:00 .. 2026-06-12T10:11:00+00:00\n蒜頭王八"
    chat_doc = "[chat] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:05:00+00:00\n777 梗"
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [[qa_doc, chat_doc]],
        "metadatas": [[
            {"source": "qa", "period_end": "2026-06-12T10:11:00+00:00"},
            {"source": "chat", "period_end": "2026-06-12T10:05:00+00:00"},
        ]],
    }
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    chromadb = MagicMock()
    chromadb.PersistentClient.return_value = mock_client
    monkeypatch.setitem(__import__("sys").modules, "chromadb", chromadb)
    return mock_collection


def test_chroma_summary_store_excludes_qa_memory_when_mode_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QA_MEMORY_MODE", "none")
    store = _setup_store_with_qa_and_chat(tmp_path)
    _mock_chroma(monkeypatch)

    knowledge = ChromaSummaryKnowledgeStore(
        store,
        session_id=None,
        chroma_dir=tmp_path / "chroma",
    )
    snippet = knowledge.query("蒜頭王八", channel="room_a")

    assert "777" in snippet or "梗" in snippet
    assert "蒜頭王八" not in snippet
    upsert_sources = {
        meta["source"] for meta in knowledge._collection.upsert.call_args.kwargs["metadatas"]
    }
    assert upsert_sources == {"chat"}
    store.close()


def test_chroma_summary_store_includes_qa_memory_when_mode_structured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QA_MEMORY_MODE", "structured")
    store = _setup_store_with_qa_and_chat(tmp_path)
    _mock_chroma(monkeypatch)

    knowledge = ChromaSummaryKnowledgeStore(
        store,
        session_id=None,
        chroma_dir=tmp_path / "chroma",
    )
    snippet = knowledge.query("蒜頭王八", channel="room_a")

    assert "蒜頭王八" in snippet
    upsert_sources = {
        meta["source"] for meta in knowledge._collection.upsert.call_args.kwargs["metadatas"]
    }
    assert upsert_sources == {"chat", "qa"}
    store.close()


def test_chroma_summary_store_excludes_qa_for_current_activity_question(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QA_MEMORY_MODE", "structured")
    store = _setup_store_with_qa_and_chat(tmp_path)
    _mock_chroma(monkeypatch)

    knowledge = ChromaSummaryKnowledgeStore(
        store,
        session_id=None,
        chroma_dir=tmp_path / "chroma",
    )
    snippet = knowledge.query("主播剛剛在幹嘛", channel="room_a")

    assert snippet == ""
    store.close()
