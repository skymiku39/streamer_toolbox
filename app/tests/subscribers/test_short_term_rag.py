from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from sub_llm.short_term_rag import SHORT_TERM_MARKER, ShortTermRagStore


def _matches(metadata: dict[str, Any], where: dict[str, Any] | None) -> bool:
    if not where:
        return True
    return all(metadata.get(key) == value for key, value in where.items())


class FakeCollection:
    """以 Python dict 模擬 Chroma collection，question 完全相符者視為最相關。"""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def add(self, *, ids, documents, metadatas) -> None:
        for doc_id, document, metadata in zip(ids, documents, metadatas, strict=False):
            self.records[doc_id] = {"document": document, "metadata": metadata}

    def get(self, *, where=None):
        ids, documents, metadatas = [], [], []
        for doc_id, record in self.records.items():
            if not _matches(record["metadata"], where):
                continue
            ids.append(doc_id)
            documents.append(record["document"])
            metadatas.append(record["metadata"])
        return {"ids": ids, "documents": documents, "metadatas": metadatas}

    def query(self, *, query_texts, n_results, where=None):
        query_text = query_texts[0]
        items = [
            (doc_id, record)
            for doc_id, record in self.records.items()
            if _matches(record["metadata"], where)
        ]
        items.sort(
            key=lambda kv: (
                kv[1]["metadata"].get("question") != query_text,
                -float(kv[1]["metadata"].get("ts", 0)),
            )
        )
        items = items[:n_results]
        return {
            "ids": [[doc_id for doc_id, _ in items]],
            "documents": [[record["document"] for _, record in items]],
            "metadatas": [[record["metadata"] for _, record in items]],
        }

    def delete(self, *, ids) -> None:
        for doc_id in ids:
            self.records.pop(doc_id, None)


def _store(monkeypatch, collection, *, now=None, **kwargs) -> ShortTermRagStore:
    chromadb = MagicMock()
    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    chromadb.EphemeralClient.return_value = client
    monkeypatch.setitem(sys.modules, "chromadb", chromadb)
    return ShortTermRagStore(now=now, **kwargs)


def test_index_then_query_returns_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(monkeypatch, FakeCollection())
    store.index("demo", "今天玩什麼", "在玩 DND 第五版")
    text = store.query("demo", "今天玩什麼")
    assert SHORT_TERM_MARKER in text
    assert "今天玩什麼" in text
    assert "DND 第五版" in text


def test_query_is_channel_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(monkeypatch, FakeCollection())
    store.index("room_a", "秘密", "答案A")
    assert store.query("room_b", "秘密") == ""


def test_empty_question_or_reply_is_not_indexed(monkeypatch: pytest.MonkeyPatch) -> None:
    collection = FakeCollection()
    store = _store(monkeypatch, collection)
    store.index("demo", "   ", "答案")
    store.index("demo", "問題", "   ")
    assert collection.records == {}


def test_entries_outside_window_are_pruned(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"t": 1000.0}
    collection = FakeCollection()
    store = _store(
        monkeypatch,
        collection,
        now=lambda: clock["t"],
        window_minutes=1,
    )
    store.index("demo", "舊問題", "舊答案")
    clock["t"] += 120
    assert store.query("demo", "舊問題") == ""
    assert collection.records == {}


def test_max_pairs_caps_history(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"t": 1000.0}
    collection = FakeCollection()
    store = _store(
        monkeypatch,
        collection,
        now=lambda: clock["t"],
        window_minutes=60,
        max_pairs=2,
    )
    for index in range(4):
        clock["t"] += 1
        store.index("demo", f"問題{index}", f"答案{index}")
    remaining = collection.get(where={"channel": "demo"})
    assert len(remaining["ids"]) == 2
    questions = {meta["question"] for meta in remaining["metadatas"]}
    assert questions == {"問題2", "問題3"}


def test_query_without_chroma_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    chromadb = MagicMock()
    chromadb.EphemeralClient.side_effect = RuntimeError("no chroma")
    monkeypatch.setitem(sys.modules, "chromadb", chromadb)
    store = ShortTermRagStore()
    store.index("demo", "問題", "答案")
    assert store.query("demo", "問題") == ""
