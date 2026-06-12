from __future__ import annotations

from typing import Protocol


class KnowledgeStore(Protocol):
    def query(self, question: str) -> str:
        """依問題檢索知識庫片段；無資料時回傳空字串。"""


class EmptyKnowledgeStore:
    """佔位實作；後續可替換為 Chroma 等 RAG 後端。"""

    def query(self, question: str) -> str:
        return ""
