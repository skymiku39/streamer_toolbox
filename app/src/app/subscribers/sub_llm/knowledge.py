from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from stream_store import ACTIVE_SESSION_KEY, StreamTextStore


class KnowledgeStore(Protocol):
    def query(self, question: str) -> str:
        """依問題檢索知識庫片段；無資料時回傳空字串。"""


class EmptyKnowledgeStore:
    def query(self, question: str) -> str:
        return ""


class CompositeKnowledgeStore:
    def __init__(self, stores: list[KnowledgeStore]) -> None:
        self._stores = stores

    def query(self, question: str) -> str:
        parts = [store.query(question).strip() for store in self._stores]
        return "\n\n".join(part for part in parts if part)


class SummaryKnowledgeStore:
    """從 L2 summaries 表讀取同 session 的 chat/stt 摘要，供 sub-llm 參考。"""

    def __init__(
        self,
        store: StreamTextStore,
        session_id: str | None,
        *,
        limit: int = 10,
        max_chars: int = 8000,
    ) -> None:
        self._store = store
        self._session_id = session_id
        self._limit = limit
        self._max_chars = max_chars

    def _resolve_session_id(self) -> str | None:
        if self._session_id:
            return self._session_id
        checkpoint = self._store.get_checkpoint(ACTIVE_SESSION_KEY)
        if checkpoint:
            return checkpoint
        return self._store.latest_session_id()

    def query(self, question: str) -> str:
        del question  # 現階段注入近期摘要全文，由 LLM 自行推理
        session_id = self._resolve_session_id()
        if session_id is None:
            return ""
        summaries = self._store.list_summaries(session_id, limit=self._limit)
        if not summaries:
            return ""
        chronological = list(reversed(summaries))
        sections: list[str] = []
        for summary in chronological:
            sections.append(
                f"[{summary.source}] {summary.period_start} .. {summary.period_end}\n"
                f"{summary.content.strip()}"
            )
        text = "\n\n".join(sections)
        if len(text) <= self._max_chars:
            return text
        return text[: self._max_chars - 3] + "..."


class FileKnowledgeStore:
    """從檔案或目錄載入文字，以簡易關鍵字評分檢索（RAG 輕量版）。"""

    _TEXT_SUFFIXES = frozenset({".md", ".txt", ".json"})

    def __init__(self, path: str | Path, *, max_snippet_chars: int = 2000) -> None:
        root = Path(path)
        self._max_snippet_chars = max_snippet_chars
        self._documents: list[str] = []
        if root.is_file():
            self._documents.append(root.read_text(encoding="utf-8"))
        elif root.is_dir():
            for file_path in sorted(root.rglob("*")):
                if file_path.is_file() and file_path.suffix.lower() in self._TEXT_SUFFIXES:
                    self._documents.append(file_path.read_text(encoding="utf-8"))

    def _query_tokens(self, question: str) -> set[str]:
        tokens = {token for token in question.lower().split() if len(token) >= 2}
        stripped = question.strip()
        for index in range(len(stripped) - 1):
            bigram = stripped[index : index + 2]
            if bigram.strip():
                tokens.add(bigram)
        return tokens

    def query(self, question: str) -> str:
        if not self._documents:
            return ""
        tokens = self._query_tokens(question)
        if not tokens:
            return ""
        best_score = 0
        best_document = ""
        for document in self._documents:
            lowered = document.lower()
            score = sum(1 for token in tokens if token in lowered)
            if score > best_score:
                best_score = score
                best_document = document
        if best_score == 0:
            return ""
        return best_document[: self._max_snippet_chars]
