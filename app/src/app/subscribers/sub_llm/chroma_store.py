from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Protocol

from sub_llm.knowledge import iter_text_documents
from sub_llm.memory_ranking import rank_memory_snippets

logger = logging.getLogger(__name__)

COLLECTION_NAME = "kb_global"
MEMORY_COLLECTION_NAME = "kb_memory"
SYNC_STATE_FILE = ".sync_fingerprint.json"
MEMORY_SYNC_STATE_FILE = ".memory_sync_fingerprint.json"


class PreloadableKnowledgeStore(Protocol):
    def preload(self) -> None:
        """程序啟動時一次性初始化；重複呼叫應為 no-op。"""


def _chunk_document(source_id: str, content: str) -> list[tuple[str, str]]:
    sections = [section.strip() for section in re.split(r"\n##\s+", content) if section.strip()]
    if not sections:
        return []
    if len(sections) == 1:
        return [(f"{source_id}#0", sections[0])]
    return [(f"{source_id}#{index}", section) for index, section in enumerate(sections)]


def _fingerprint_documents(documents: list[tuple[str, str]]) -> str:
    digest = hashlib.sha256()
    for source_id, content in sorted(documents):
        digest.update(source_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


class ChromaKnowledgeStore:
    """ChromaDB 向量知識庫：啟動時 preload 一次，僅在來源變更時重新 upsert。"""

    def __init__(
        self,
        path: str | Path,
        *,
        chroma_dir: str | Path,
        max_results: int = 3,
        max_snippet_chars: int = 2000,
    ) -> None:
        self._root = Path(path)
        self._chroma_dir = Path(chroma_dir)
        self._max_results = max_results
        self._max_snippet_chars = max_snippet_chars
        self._collection: Any | None = None
        self._client: Any | None = None
        self._preload_lock = threading.Lock()
        self._preloaded = False
        self._chroma_tried = False

    def preload(self) -> None:
        with self._preload_lock:
            if self._preloaded:
                return
            self._ensure_chroma()
            self._sync_if_needed()
            self._preloaded = True

    def _ensure_chroma(self) -> None:
        if self._chroma_tried:
            return
        self._chroma_tried = True
        try:
            import chromadb

            self._chroma_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self._chroma_dir))
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.warning("ChromaDB 初始化失敗，知識庫查詢將回傳空結果: %s", exc)
            self._collection = None

    def _sync_state_path(self) -> Path:
        return self._chroma_dir / SYNC_STATE_FILE

    def _read_sync_fingerprint(self) -> str | None:
        state_path = self._sync_state_path()
        if not state_path.is_file():
            return None
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        fingerprint = payload.get("fingerprint")
        return fingerprint if isinstance(fingerprint, str) else None

    def _write_sync_fingerprint(self, fingerprint: str) -> None:
        state_path = self._sync_state_path()
        state_path.write_text(
            json.dumps({"fingerprint": fingerprint}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _sync_if_needed(self) -> None:
        if self._collection is None or not self._root.exists():
            return

        documents = iter_text_documents(self._root)
        fingerprint = _fingerprint_documents(documents)
        if fingerprint == self._read_sync_fingerprint():
            logger.debug("Chroma 知識庫來源未變更，略過 upsert")
            return

        chunks: list[tuple[str, str]] = []
        for source_id, content in documents:
            chunks.extend(_chunk_document(source_id, content))
        if not chunks:
            return

        ids = [chunk_id for chunk_id, _ in chunks]
        texts = [text for _, text in chunks]
        self._collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=[{"source": chunk_id.rsplit("#", 1)[0]} for chunk_id, _ in chunks],
        )
        self._write_sync_fingerprint(fingerprint)
        logger.info("Chroma 知識庫已同步 %d 個片段", len(chunks))

    def query(self, question: str, *, channel: str = "") -> str:
        del channel
        if not question.strip():
            return ""
        if not self._preloaded:
            self.preload()
        if self._collection is None:
            return ""

        try:
            result = self._collection.query(
                query_texts=[question],
                n_results=self._max_results,
            )
            documents = (result.get("documents") or [[]])[0]
        except Exception as exc:
            logger.debug("Chroma 查詢失敗: %s", exc)
            return ""

        unique = list(dict.fromkeys(doc.strip() for doc in documents if doc and doc.strip()))
        if not unique:
            return ""
        text = "【實況主知識庫】\n" + "\n".join(unique)
        if len(text) <= self._max_snippet_chars:
            return text
        return text[: self._max_snippet_chars - 3] + "..."


def _fingerprint_summaries(summaries: list[Any]) -> str:
    digest = hashlib.sha256()
    for summary in summaries:
        digest.update(str(summary.id).encode("utf-8"))
        digest.update(b"\0")
        digest.update(summary.content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


class ChromaSummaryKnowledgeStore:
    """L2 摘要改由 Chroma 向量檢索，取代全文注入 SQLite 摘要。"""

    def __init__(
        self,
        store: Any,
        session_id: str | None,
        *,
        chroma_dir: str | Path,
        limit: int = 10,
        max_results: int = 5,
        max_snippet_chars: int = 4000,
        include_qa_memory: bool | None = None,
    ) -> None:
        from app.subscribers.qa_memory_mode import qa_memory_read_enabled

        self._store = store
        self._session_id = session_id
        self._chroma_dir = Path(chroma_dir)
        self._limit = limit
        self._max_results = max_results
        self._max_snippet_chars = max_snippet_chars
        self._include_qa_memory = (
            qa_memory_read_enabled() if include_qa_memory is None else include_qa_memory
        )
        self._collection: Any | None = None
        self._client: Any | None = None
        self._preload_lock = threading.Lock()
        self._preloaded = False
        self._chroma_tried = False

    def preload(self) -> None:
        with self._preload_lock:
            if self._preloaded:
                return
            self._ensure_chroma()
            self._preloaded = True

    def _ensure_chroma(self) -> None:
        if self._chroma_tried:
            return
        self._chroma_tried = True
        try:
            import chromadb

            self._chroma_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self._chroma_dir))
            self._collection = self._client.get_or_create_collection(
                name=MEMORY_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.warning("Chroma 記憶庫初始化失敗: %s", exc)
            self._collection = None

    def _memory_sync_state_path(self) -> Path:
        return self._chroma_dir / MEMORY_SYNC_STATE_FILE

    def _read_memory_fingerprints(self) -> dict[str, str]:
        state_path = self._memory_sync_state_path()
        if not state_path.is_file():
            return {}
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in payload.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def _write_memory_fingerprint(self, session_id: str, fingerprint: str) -> None:
        fingerprints = self._read_memory_fingerprints()
        fingerprints[session_id] = fingerprint
        self._memory_sync_state_path().write_text(
            json.dumps(fingerprints, ensure_ascii=False),
            encoding="utf-8",
        )

    def _sync_session_summaries(self, session_id: str) -> None:
        if self._collection is None:
            return

        summaries = self._store.list_summaries(session_id, limit=self._limit)
        chronological = list(reversed(summaries))
        if not self._include_qa_memory:
            chronological = [item for item in chronological if item.source != "qa"]
        fingerprint = _fingerprint_summaries(chronological)
        if self._read_memory_fingerprints().get(session_id) == fingerprint:
            return
        if not chronological:
            return

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str]] = []
        for summary in chronological:
            ids.append(f"summary_{summary.id}")
            documents.append(
                f"[{summary.source}] {summary.period_start} .. {summary.period_end}\n"
                f"{summary.content.strip()}"
            )
            metadatas.append(
                {
                    "session_id": session_id,
                    "source": summary.source,
                    "period_end": summary.period_end,
                }
            )

        if not ids:
            return

        self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        self._write_memory_fingerprint(session_id, fingerprint)
        logger.info("Chroma 記憶庫已同步 session=%s 共 %d 筆摘要", session_id, len(chronological))

    def query(self, question: str, *, channel: str = "") -> str:
        from stream_store import resolve_session_for_channel

        if not question.strip():
            return ""
        if not self._preloaded:
            self.preload()
        if self._collection is None:
            return ""

        session_id = resolve_session_for_channel(
            self._store,
            channel,
            explicit_session_id=self._session_id,
        )
        if session_id is None:
            return ""

        self._sync_session_summaries(session_id)
        try:
            result = self._collection.query(
                query_texts=[question],
                n_results=self._max_results,
                where={"session_id": session_id},
            )
            documents = (result.get("documents") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]
        except Exception as exc:
            logger.debug("Chroma 記憶查詢失敗: %s", exc)
            return ""

        if not self._include_qa_memory:
            filtered_docs: list[str] = []
            filtered_metas: list[dict[str, str]] = []
            for doc, meta in zip(documents, metadatas, strict=False):
                if (meta or {}).get("source") == "qa":
                    continue
                filtered_docs.append(doc)
                filtered_metas.append(meta or {})
            documents = filtered_docs
            metadatas = filtered_metas

        unique = rank_memory_snippets(documents, metadatas)
        if not unique:
            return ""
        text = (
            "【近期直播摘要】（依時間由新到舊；僅描述過去發生什麼，"
            "勿把摘要裡 bot 曾回「沒提到」當成回答模板）\n"
            + "\n".join(unique)
        )
        if len(text) <= self._max_snippet_chars:
            return text
        return text[: self._max_snippet_chars - 3] + "..."
