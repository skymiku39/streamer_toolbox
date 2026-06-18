from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Protocol

from stream_store.session import normalize_channel
from sub_llm.embedding import resolve_embedding_function
from sub_llm.knowledge import iter_text_documents
from sub_llm.live_activity import is_current_activity_question
from sub_llm.prompt_format import (
    INTRA_SEP,
    compact_markdown,
    format_memory_snippet_for_prompt,
    is_placeholder_knowledge,
)
from sub_llm.memory_category import CATEGORY_FACT, CATEGORY_LORE, category_label
from sub_llm.memory_ranking import rank_memory_snippets
from sub_llm.session_recap import should_enrich_session_recap

logger = logging.getLogger(__name__)

COLLECTION_NAME = "kb_global"
MEMORY_COLLECTION_NAME = "kb_memory"
SYNC_STATE_FILE = ".sync_fingerprint.json"
MEMORY_SYNC_STATE_FILE = ".memory_sync_fingerprint.json"

# 記憶索引結構版本：metadata 欄位或索引策略變更時遞增，
# 併入 fingerprint 以強制既有 session 重新索引一次。
_MEMORY_INDEX_SCHEMA = "2"

# 跨 session 檢索時放寬 session 限制的高可信度類別（頻道穩定事實／固定梗）。
_CROSS_SESSION_CATEGORIES = (CATEGORY_FACT, CATEGORY_LORE)


def _first_distances(raw: Any, count: int) -> list[float | None]:
    """從 Chroma 查詢結果取出第一組 distances，並對齊文件數量（不足補 None）。"""
    rows = raw or [[]]
    values = list(rows[0]) if rows else []
    aligned: list[float | None] = []
    for index in range(count):
        if index < len(values) and values[index] is not None:
            try:
                aligned.append(float(values[index]))
            except (TypeError, ValueError):
                aligned.append(None)
        else:
            aligned.append(None)
    return aligned


def _collection_embedding_kwargs() -> dict[str, Any]:
    embedding_function = resolve_embedding_function()
    if embedding_function is None:
        return {}
    return {"embedding_function": embedding_function}


def _channel_from_session(session_id: str) -> str:
    """從 session_id（{channel}_{YYYYMMDD}）回推 normalized channel；無法判斷時回傳空字串。"""
    prefix, _, suffix = session_id.rpartition("_")
    if prefix and len(suffix) == 8 and suffix.isdigit():
        return prefix
    return ""


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


_QUERY_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{2,}")


def _query_tokens(question: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(token.casefold() for token in _QUERY_TOKEN_RE.findall(question))
    )


def _keyword_overlap_score(question: str, document: str) -> int:
    haystack = document.casefold()
    return sum(1 for token in _query_tokens(question) if token in haystack)


def _rerank_by_keyword_overlap(question: str, documents: list[str]) -> list[str]:
    if len(documents) <= 1:
        return documents
    scored = [(doc, _keyword_overlap_score(question, doc)) for doc in documents]
    if max(score for _, score in scored) <= 0:
        return documents
    return [
        doc
        for doc, _ in sorted(
            scored,
            key=lambda item: (-item[1], documents.index(item[0])),
        )
    ]


def _usable_knowledge_chunks(documents: list[str]) -> list[str]:
    """剔除 chunk 內的模板占位行，保留可用片段（避免整段因一行 placeholder 被丟棄）。"""
    usable: list[str] = []
    for document in documents:
        kept: list[str] = []
        for line in document.splitlines():
            stripped = line.strip()
            if not stripped or is_placeholder_knowledge(stripped):
                continue
            kept.append(stripped)
        if not kept:
            continue
        text = compact_markdown("\n".join(kept))
        if text:
            usable.append(text)
    return usable


def _lexical_chunk_matches(question: str, root: Path, *, limit: int) -> list[str]:
    """向量未命中時，以關鍵字比對本地知識庫 chunk（適用梗語、數字等短查詢）。"""
    tokens = _query_tokens(question)
    if not tokens or not root.exists():
        return []
    scored: list[tuple[str, int]] = []
    for source_id, content in iter_text_documents(root):
        for _, chunk in _chunk_document(source_id, content):
            score = _keyword_overlap_score(question, chunk)
            if score > 0:
                scored.append((chunk, score))
    if not scored:
        return []
    scored.sort(key=lambda item: (-item[1], item[0]))
    unique: list[str] = []
    for chunk, _ in scored:
        if chunk not in unique:
            unique.append(chunk)
        if len(unique) >= limit:
            break
    return unique


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
                **_collection_embedding_kwargs(),
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
            total = int(self._collection.count())
        except (TypeError, ValueError):
            total = 0
        n_results = min(total, max(self._max_results, 10)) if total else self._max_results
        try:
            result = self._collection.query(
                query_texts=[question],
                n_results=n_results,
            )
            documents = (result.get("documents") or [[]])[0]
        except Exception as exc:
            logger.debug("Chroma 查詢失敗: %s", exc)
            return ""

        unique = list(dict.fromkeys(doc.strip() for doc in documents if doc and doc.strip()))
        if not unique or _keyword_overlap_score(question, unique[0]) == 0:
            lexical = _lexical_chunk_matches(
                question,
                self._root,
                limit=self._max_results,
            )
            if lexical:
                unique = list(dict.fromkeys(lexical + unique))
        unique = _rerank_by_keyword_overlap(question, unique)[: self._max_results]
        usable = _usable_knowledge_chunks(unique)
        if not usable:
            return ""
        text = "知識:" + INTRA_SEP.join(usable)
        if len(text) <= self._max_snippet_chars:
            return text
        return text[: self._max_snippet_chars - 3] + "..."


def _fingerprint_summaries(summaries: list[Any]) -> str:
    digest = hashlib.sha256()
    digest.update(_MEMORY_INDEX_SCHEMA.encode("utf-8"))
    digest.update(b"\0")
    for summary in summaries:
        digest.update(str(summary.id).encode("utf-8"))
        digest.update(b"\0")
        digest.update(summary.content.encode("utf-8"))
        digest.update(b"\0")
        digest.update((getattr(summary, "category", "") or "").encode("utf-8"))
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
        cross_session_lore: bool = True,
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
        self._cross_session_lore = cross_session_lore
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
                **_collection_embedding_kwargs(),
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

    def sync(self, session_id: str, *, channel: str = "") -> None:
        """主動為指定 session 索引摘要；可由事件驅動（memory.summary.ready）呼叫。"""
        if not self._preloaded:
            self.preload()
        self._sync_session_summaries(session_id, channel=channel)

    def _purge_stale_summaries(self, session_id: str, keep_ids: set[str]) -> None:
        """刪除已跌出同步視窗（或來源被過濾）的舊向量，避免檢索到過期片段。"""
        if self._collection is None:
            return
        try:
            existing = self._collection.get(where={"session_id": session_id})
            existing_ids = list(existing.get("ids") or [])
            stale = [doc_id for doc_id in existing_ids if doc_id not in keep_ids]
            if stale:
                self._collection.delete(ids=stale)
                logger.info(
                    "Chroma 記憶庫清除過期向量 session=%s 共 %d 筆", session_id, len(stale)
                )
        except Exception as exc:
            logger.debug("Chroma 記憶清除過期向量失敗: %s", exc)

    def _sync_session_summaries(self, session_id: str, *, channel: str = "") -> None:
        if self._collection is None:
            return

        summaries = self._store.list_summaries(session_id, limit=self._limit)
        chronological = list(reversed(summaries))
        if not self._include_qa_memory:
            chronological = [item for item in chronological if item.source != "qa"]
        fingerprint = _fingerprint_summaries(chronological)
        if self._read_memory_fingerprints().get(session_id) == fingerprint:
            return

        normalized_channel = (
            normalize_channel(channel) if channel else _channel_from_session(session_id)
        )

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str]] = []
        for summary in chronological:
            ids.append(f"summary_{summary.id}")
            category = getattr(summary, "category", "") or ""
            # qa 記憶帶分類標籤（位於時間 header 之後，header 被剝除後仍保留），
            # 讓低可信度（八卦／討論）在 prompt 內可見。
            body = summary.content.strip()
            if summary.source == "qa":
                label = category_label(category)
                body = f"[{label}]{body}"
            documents.append(
                f"[{summary.source}] {summary.period_start} .. {summary.period_end}\n"
                f"{body}"
            )
            metadatas.append(
                {
                    "session_id": session_id,
                    "channel": normalized_channel,
                    "source": summary.source,
                    "period_end": summary.period_end,
                    "category": category,
                }
            )

        # 即使本次無摘要（例如 qa 全被過濾）仍要清除既有過期向量並落地 fingerprint。
        self._purge_stale_summaries(session_id, set(ids))
        if ids:
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

        self._sync_session_summaries(session_id, channel=channel)
        if is_current_activity_question(question):
            return ""

        try:
            result = self._collection.query(
                query_texts=[question],
                n_results=self._max_results,
                where={"session_id": session_id},
            )
            documents = list((result.get("documents") or [[]])[0])
            metadatas = list((result.get("metadatas") or [[]])[0])
            distances = _first_distances(result.get("distances"), len(documents))
        except Exception as exc:
            logger.debug("Chroma 記憶查詢失敗: %s", exc)
            return ""

        cross_docs, cross_metas, cross_dists = self._query_cross_session_lore(
            question, channel=channel, exclude_session_id=session_id
        )
        documents.extend(cross_docs)
        metadatas.extend(cross_metas)
        distances.extend(cross_dists)

        exclude_qa_memory = (
            not self._include_qa_memory
            or is_current_activity_question(question)
            or should_enrich_session_recap(question)
        )
        if exclude_qa_memory:
            filtered_docs: list[str] = []
            filtered_metas: list[dict[str, str]] = []
            filtered_dists: list[float | None] = []
            for doc, meta, dist in zip(documents, metadatas, distances, strict=False):
                if (meta or {}).get("source") == "qa":
                    continue
                filtered_docs.append(doc)
                filtered_metas.append(meta or {})
                filtered_dists.append(dist)
            documents = filtered_docs
            metadatas = filtered_metas
            distances = filtered_dists

        unique = rank_memory_snippets(documents, metadatas, distances)
        if not unique:
            return ""
        snippets = [format_memory_snippet_for_prompt(doc) for doc in unique]
        text = "記憶:" + INTRA_SEP.join(snippets)
        if len(text) <= self._max_snippet_chars:
            return text
        return text[: self._max_snippet_chars - 3] + "..."

    def _query_cross_session_lore(
        self,
        question: str,
        *,
        channel: str,
        exclude_session_id: str,
    ) -> tuple[list[str], list[dict[str, str]], list[float | None]]:
        """跨 session 檢索同頻道高可信度記憶（事實／固定梗），不受當前 session 限制。"""
        if self._collection is None or not self._cross_session_lore:
            return [], [], []
        normalized_channel = normalize_channel(channel) if channel else ""
        if not normalized_channel:
            return [], [], []
        try:
            result = self._collection.query(
                query_texts=[question],
                n_results=self._max_results,
                where={
                    "$and": [
                        {"channel": normalized_channel},
                        {"category": {"$in": list(_CROSS_SESSION_CATEGORIES)}},
                    ]
                },
            )
            documents = list((result.get("documents") or [[]])[0])
            metadatas = list((result.get("metadatas") or [[]])[0])
            distances = _first_distances(result.get("distances"), len(documents))
        except Exception as exc:
            logger.debug("Chroma 跨 session 記憶查詢失敗: %s", exc)
            return [], [], []

        kept_docs: list[str] = []
        kept_metas: list[dict[str, str]] = []
        kept_dists: list[float | None] = []
        for doc, meta, dist in zip(documents, metadatas, distances, strict=False):
            meta = meta or {}
            if meta.get("session_id") == exclude_session_id:
                continue
            kept_docs.append(doc)
            kept_metas.append(meta)
            kept_dists.append(dist)
        return kept_docs, kept_metas, kept_dists
