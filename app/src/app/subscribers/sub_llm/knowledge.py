from __future__ import annotations

from pathlib import Path
from typing import Protocol

from stream_store import StreamTextStore, resolve_session_for_channel

from sub_llm.prompt_format import GROUP_SEP

_TEXT_SUFFIXES = frozenset({".md", ".txt", ".json"})


def iter_text_documents(root: Path) -> list[tuple[str, str]]:
    """載入知識庫檔案，回傳 (來源識別, 內容) 列表。"""
    documents: list[tuple[str, str]] = []
    if root.is_file():
        documents.append((root.name, root.read_text(encoding="utf-8")))
    elif root.is_dir():
        for file_path in sorted(root.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in _TEXT_SUFFIXES:
                rel = file_path.relative_to(root).as_posix()
                documents.append((rel, file_path.read_text(encoding="utf-8")))
    return documents


class KnowledgeStore(Protocol):
    def query(self, question: str, *, channel: str = "") -> str:
        """依問題與直播間 channel 檢索知識庫片段；無資料時回傳空字串。"""


class EmptyKnowledgeStore:
    def query(self, question: str, *, channel: str = "") -> str:
        return ""


class CompositeKnowledgeStore:
    def __init__(self, stores: list[KnowledgeStore]) -> None:
        self._stores = stores

    def preload(self) -> None:
        for store in self._stores:
            preload = getattr(store, "preload", None)
            if callable(preload):
                preload()

    def query(self, question: str, *, channel: str = "") -> str:
        parts = [store.query(question, channel=channel).strip() for store in self._stores]
        return GROUP_SEP.join(part for part in parts if part)

    def sync(self, session_id: str, *, channel: str = "") -> None:
        for store in self._stores:
            sync = getattr(store, "sync", None)
            if callable(sync):
                sync(session_id, channel=channel)


class SummaryKnowledgeStore:
    """從 L2 summaries 表讀取同 channel 對應 session 的 chat/stt 摘要（非 RAG，僅供測試）。"""

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

    def query(self, question: str, *, channel: str = "") -> str:
        del question  # 現階段注入近期摘要全文，由 LLM 自行推理
        session_id = resolve_session_for_channel(
            self._store,
            channel,
            explicit_session_id=self._session_id,
        )
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

    def __init__(self, path: str | Path, *, max_snippet_chars: int = 2000) -> None:
        self._max_snippet_chars = max_snippet_chars
        self._documents = [content for _, content in iter_text_documents(Path(path))]

    def _query_tokens(self, question: str) -> set[str]:
        tokens = {token for token in question.lower().split() if len(token) >= 2}
        stripped = question.strip()
        for index in range(len(stripped) - 1):
            bigram = stripped[index : index + 2]
            if bigram.strip():
                tokens.add(bigram)
        return tokens

    def query(self, question: str, *, channel: str = "") -> str:
        del channel
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
