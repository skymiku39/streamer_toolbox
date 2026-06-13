from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Protocol

from sub_llm.knowledge import iter_text_documents

logger = logging.getLogger(__name__)

COLLECTION_NAME = "kb_global"
SYNC_STATE_FILE = ".sync_fingerprint.json"


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
