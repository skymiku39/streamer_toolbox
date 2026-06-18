from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from stream_store import StreamTextStore, set_active_session_for_channel
from sub_llm.chroma_store import ChromaSummaryKnowledgeStore


def _match_where(meta: dict[str, Any], where: dict[str, Any] | None) -> bool:
    if not where:
        return True
    if "$and" in where:
        return all(_match_where(meta, sub) for sub in where["$and"])
    for key, value in where.items():
        if isinstance(value, dict) and "$in" in value:
            if meta.get(key) not in value["$in"]:
                return False
        elif meta.get(key) != value:
            return False
    return True


class FakeCollection:
    """以 dict 模擬 Chroma collection，支援 upsert/get/delete/query（含 $and、$in）。"""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def upsert(self, *, ids, documents, metadatas) -> None:
        for doc_id, document, metadata in zip(ids, documents, metadatas, strict=False):
            self.records[doc_id] = {"document": document, "metadata": metadata}

    def get(self, *, where=None):
        ids, documents, metadatas = [], [], []
        for doc_id, record in self.records.items():
            if not _match_where(record["metadata"], where):
                continue
            ids.append(doc_id)
            documents.append(record["document"])
            metadatas.append(record["metadata"])
        return {"ids": ids, "documents": documents, "metadatas": metadatas}

    def delete(self, *, ids) -> None:
        for doc_id in ids:
            self.records.pop(doc_id, None)

    def query(self, *, query_texts, n_results, where=None):
        matched = [
            record
            for record in self.records.values()
            if _match_where(record["metadata"], where)
        ][:n_results]
        return {
            "documents": [[record["document"] for record in matched]],
            "metadatas": [[record["metadata"] for record in matched]],
        }


def _store_with_fake_chroma(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    collection: FakeCollection,
) -> StreamTextStore:
    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    chromadb = MagicMock()
    chromadb.PersistentClient.return_value = client
    monkeypatch.setitem(__import__("sys").modules, "chromadb", chromadb)
    return StreamTextStore(tmp_path / "test.db")


def test_sync_purges_summaries_dropped_from_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    collection = FakeCollection()
    store = _store_with_fake_chroma(tmp_path, monkeypatch, collection)
    first = store.save_summary(
        session_id="demo_20260101",
        period_start="2026-01-01T10:00:00+00:00",
        period_end="2026-01-01T10:05:00+00:00",
        source="chat",
        content="第一段",
        record_count=1,
    )
    knowledge = ChromaSummaryKnowledgeStore(
        store,
        session_id=None,
        chroma_dir=tmp_path / "chroma",
        limit=2,
        include_qa_memory=True,
    )
    knowledge.sync("demo_20260101", channel="demo")
    assert f"summary_{first.id}" in collection.records

    store.save_summary(
        session_id="demo_20260101",
        period_start="2026-01-01T10:06:00+00:00",
        period_end="2026-01-01T10:10:00+00:00",
        source="chat",
        content="第二段",
        record_count=1,
    )
    store.save_summary(
        session_id="demo_20260101",
        period_start="2026-01-01T10:11:00+00:00",
        period_end="2026-01-01T10:15:00+00:00",
        source="chat",
        content="第三段",
        record_count=1,
    )
    knowledge.sync("demo_20260101", channel="demo")

    # limit=2，最舊的第一段應被清除，僅保留最新兩筆。
    assert f"summary_{first.id}" not in collection.records
    assert len(collection.records) == 2
    store.close()


def test_query_includes_cross_session_lore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    collection = FakeCollection()
    store = _store_with_fake_chroma(tmp_path, monkeypatch, collection)
    store.save_summary(
        session_id="demo_20260101",
        period_start="2026-01-01T10:00:00+00:00",
        period_end="2026-01-01T10:05:00+00:00",
        source="chat",
        content="主播的麥克風是 Shure SM7B",
        record_count=1,
        category="fact",
    )
    store.save_summary(
        session_id="demo_20260102",
        period_start="2026-01-02T10:00:00+00:00",
        period_end="2026-01-02T10:05:00+00:00",
        source="chat",
        content="今天在打王",
        record_count=1,
        category="progress",
    )
    set_active_session_for_channel(store, channel="demo", session_id="demo_20260102")

    knowledge = ChromaSummaryKnowledgeStore(
        store,
        session_id=None,
        chroma_dir=tmp_path / "chroma",
        include_qa_memory=True,
    )
    # 先索引舊場次的事實記憶（模擬該場結束後留存的向量）。
    knowledge.sync("demo_20260101", channel="demo")

    snippet = knowledge.query("主播用什麼麥克風", channel="demo")
    assert "SM7B" in snippet
    store.close()


def test_query_cross_session_lore_can_be_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    collection = FakeCollection()
    store = _store_with_fake_chroma(tmp_path, monkeypatch, collection)
    store.save_summary(
        session_id="demo_20260101",
        period_start="2026-01-01T10:00:00+00:00",
        period_end="2026-01-01T10:05:00+00:00",
        source="chat",
        content="主播的麥克風是 Shure SM7B",
        record_count=1,
        category="fact",
    )
    set_active_session_for_channel(store, channel="demo", session_id="demo_20260102")

    knowledge = ChromaSummaryKnowledgeStore(
        store,
        session_id=None,
        chroma_dir=tmp_path / "chroma",
        include_qa_memory=True,
        cross_session_lore=False,
    )
    knowledge.sync("demo_20260101", channel="demo")

    snippet = knowledge.query("主播用什麼麥克風", channel="demo")
    assert "SM7B" not in snippet
    store.close()
