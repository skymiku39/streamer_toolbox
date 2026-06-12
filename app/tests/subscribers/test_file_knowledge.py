from __future__ import annotations

from pathlib import Path

from sub_llm.knowledge import FileKnowledgeStore


def test_file_knowledge_store_matches_keywords(tmp_path: Path) -> None:
    (tmp_path / "faq.md").write_text("直播時間是週五晚上八點。", encoding="utf-8")
    store = FileKnowledgeStore(tmp_path)
    snippet = store.query("請問直播時間？")
    assert "週五" in snippet


def test_file_knowledge_store_returns_empty_when_no_match(tmp_path: Path) -> None:
    (tmp_path / "faq.md").write_text("完全不同內容", encoding="utf-8")
    store = FileKnowledgeStore(tmp_path)
    assert store.query("xyz unknown token") == ""
