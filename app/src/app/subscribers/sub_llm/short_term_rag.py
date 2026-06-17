from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from stream_store.session import normalize_channel

from sub_llm.prompt_format import INTRA_SEP

logger = logging.getLogger(__name__)

SHORT_TERM_COLLECTION = "kb_shortterm"
SHORT_TERM_MARKER = "Bot記憶:"


class ShortTermRagStore:
    """程序內短期記憶 RAG：以 in-memory Chroma 檢索近期 Bot 問答，重啟即清空。"""

    def __init__(
        self,
        *,
        window_minutes: int = 30,
        max_pairs: int = 20,
        max_results: int = 3,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._window_seconds = max(1, window_minutes) * 60
        self._max_pairs = max(1, max_pairs)
        self._max_results = max(1, max_results)
        self._now = now or time.time
        self._collection: Any | None = None
        self._client: Any | None = None
        self._lock = threading.Lock()
        self._chroma_tried = False

    def _ensure_chroma(self) -> None:
        if self._chroma_tried:
            return
        self._chroma_tried = True
        try:
            import chromadb

            self._client = chromadb.EphemeralClient()
            self._collection = self._client.get_or_create_collection(
                name=SHORT_TERM_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.warning("短期記憶 Chroma 初始化失敗，將略過短期 RAG: %s", exc)
            self._collection = None

    def index(
        self,
        channel: str,
        question: str,
        reply: str,
        *,
        timestamp: float | None = None,
    ) -> None:
        normalized_question = question.strip()
        normalized_reply = reply.strip()
        if not normalized_question or not normalized_reply:
            return
        with self._lock:
            self._ensure_chroma()
            if self._collection is None:
                return
            ts = timestamp if timestamp is not None else self._now()
            try:
                self._collection.add(
                    ids=[uuid.uuid4().hex],
                    documents=[normalized_question],
                    metadatas=[
                        {
                            "channel": normalize_channel(channel),
                            "ts": float(ts),
                            "question": normalized_question,
                            "reply": normalized_reply,
                        }
                    ],
                )
            except Exception as exc:
                logger.debug("短期記憶寫入失敗: %s", exc)
                return
            self._prune_locked(channel)

    def query(self, channel: str, question: str) -> str:
        normalized_question = question.strip()
        if not normalized_question:
            return ""
        with self._lock:
            self._ensure_chroma()
            if self._collection is None:
                return ""
            self._prune_locked(channel)
            try:
                result = self._collection.query(
                    query_texts=[normalized_question],
                    n_results=self._max_results,
                    where={"channel": normalize_channel(channel)},
                )
                metadatas = (result.get("metadatas") or [[]])[0]
            except Exception as exc:
                logger.debug("短期記憶查詢失敗: %s", exc)
                return ""

        cutoff = self._now() - self._window_seconds
        pairs: list[tuple[str, str]] = []
        for meta in metadatas:
            meta = meta or {}
            if float(meta.get("ts", 0)) < cutoff:
                continue
            stored_question = str(meta.get("question", "")).strip()
            stored_reply = str(meta.get("reply", "")).strip()
            if stored_question and stored_reply:
                pairs.append((stored_question, stored_reply))
        if not pairs:
            return ""

        pairs_text = INTRA_SEP.join(
            f"{stored_question}→{stored_reply}" for stored_question, stored_reply in pairs
        )
        return f"{SHORT_TERM_MARKER}{pairs_text}"

    def _prune_locked(self, channel: str) -> None:
        if self._collection is None:
            return
        try:
            data = self._collection.get(where={"channel": normalize_channel(channel)})
        except Exception:
            return
        ids = data.get("ids") or []
        metadatas = data.get("metadatas") or []
        cutoff = self._now() - self._window_seconds
        stale: list[str] = []
        fresh: list[tuple[float, str]] = []
        for doc_id, meta in zip(ids, metadatas, strict=False):
            ts = float((meta or {}).get("ts", 0))
            if ts < cutoff:
                stale.append(doc_id)
            else:
                fresh.append((ts, doc_id))
        if len(fresh) > self._max_pairs:
            fresh.sort(key=lambda item: item[0])
            overflow = len(fresh) - self._max_pairs
            stale.extend(doc_id for _, doc_id in fresh[:overflow])
        if stale:
            try:
                self._collection.delete(ids=stale)
            except Exception:
                pass
