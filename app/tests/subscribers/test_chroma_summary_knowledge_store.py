from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from stream_store import StreamTextStore, set_active_session_for_channel
from sub_llm.chroma_store import ChromaSummaryKnowledgeStore


def test_chroma_summary_store_queries_by_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "test.db"
    chroma_dir = tmp_path / "chroma"
    store = StreamTextStore(db_path)
    store.save_summary(
        session_id="room_a_20260612",
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="觀眾在問 777 梗",
        record_count=1,
    )
    store.save_summary(
        session_id="room_b_20260612",
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="另一個房間內容",
        record_count=1,
    )
    set_active_session_for_channel(store, channel="room_a", session_id="room_a_20260612")
    set_active_session_for_channel(store, channel="room_b", session_id="room_b_20260612")

    older_doc = "[chat] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:05:00+00:00\n舊梗"
    newer_doc = "[chat] 2026-06-12T10:30:00+00:00 .. 2026-06-12T10:35:00+00:00\n觀眾在問 777 梗"

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [[older_doc, newer_doc]],
        "metadatas": [[
            {"period_end": "2026-06-12T10:05:00+00:00"},
            {"period_end": "2026-06-12T10:35:00+00:00"},
        ]],
    }
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    chromadb = MagicMock()
    chromadb.PersistentClient.return_value = mock_client
    monkeypatch.setitem(__import__("sys").modules, "chromadb", chromadb)

    knowledge = ChromaSummaryKnowledgeStore(store, session_id=None, chroma_dir=chroma_dir)
    snippet = knowledge.query("777 是什麼", channel="room_a")

    assert "記憶:" in snippet
    assert snippet.index("777") < snippet.index("舊梗")
    mock_collection.upsert.assert_called_once()
    upsert_metas = mock_collection.upsert.call_args.kwargs["metadatas"]
    assert upsert_metas[0]["period_end"] == "2026-06-12T10:05:00+00:00"
    # 主查詢以當前 session 為範圍；其後另有跨 session 的事實/梗檢索（B3）。
    primary_where = mock_collection.query.call_args_list[0].kwargs["where"]
    assert primary_where == {"session_id": "room_a_20260612"}
    store.close()
