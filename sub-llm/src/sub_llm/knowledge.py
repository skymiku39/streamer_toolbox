from __future__ import annotations

from pathlib import Path
from typing import Protocol


class KnowledgeStore(Protocol):
    def query(self, question: str) -> str:
        """依問題檢索知識庫片段；無資料時回傳空字串。"""


class EmptyKnowledgeStore:
    def query(self, question: str) -> str:
        return ""


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
