from __future__ import annotations

import os

from stream_store import StreamTextStore

from sub_llm.chroma_store import ChromaKnowledgeStore, ChromaSummaryKnowledgeStore
from sub_llm.knowledge import (
    CompositeKnowledgeStore,
    EmptyKnowledgeStore,
    KnowledgeStore,
)
from sub_llm.llm import LlmClient, TemplateLlmClient
from sub_llm.openai_client import OpenAiCompatibleLlmClient


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


_DEFAULT_KNOWLEDGE_BACKEND = "chroma"


def _knowledge_backend() -> str:
    backend = (
        os.environ.get("LLM_KNOWLEDGE_BACKEND", _DEFAULT_KNOWLEDGE_BACKEND)
        or _DEFAULT_KNOWLEDGE_BACKEND
    ).strip().lower()
    if backend == "file":
        raise ValueError(
            "LLM_KNOWLEDGE_BACKEND=file 已停用（非 RAG）。"
            "請設 LLM_KNOWLEDGE_BACKEND=chroma 以使用 Chroma 向量檢索。"
        )
    if backend != "chroma":
        raise ValueError(f"unsupported LLM_KNOWLEDGE_BACKEND: {backend!r}（僅支援 chroma RAG）")
    return backend


def create_llm_client(backend: str | None = None) -> LlmClient:
    selected = (backend or os.environ.get("LLM_BACKEND", "template") or "template").lower()
    if selected == "template":
        return TemplateLlmClient()
    if selected in {"openai", "gemini"}:
        return OpenAiCompatibleLlmClient.from_env(backend=selected)
    raise ValueError(f"unsupported LLM_BACKEND: {selected!r}")


def _chroma_dir() -> str:
    return (os.environ.get("LLM_CHROMA_DIR", "data/chroma") or "data/chroma").strip()


def _create_summary_store() -> KnowledgeStore:
    _knowledge_backend()
    db_path = os.environ.get("STREAM_DB_PATH", "data/stream_text.db")
    session_id = (os.environ.get("STREAM_SESSION_ID") or "").strip() or None
    limit = int(os.environ.get("LLM_MEMORY_SUMMARY_LIMIT", "10"))
    memory_query_limit = int(os.environ.get("LLM_CHROMA_MEMORY_QUERY_LIMIT", "5"))
    store = StreamTextStore(db_path)
    return ChromaSummaryKnowledgeStore(
        store,
        session_id,
        chroma_dir=_chroma_dir(),
        limit=limit,
        max_results=memory_query_limit,
    )


def _create_static_knowledge_store(knowledge_path: str) -> KnowledgeStore:
    _knowledge_backend()
    query_limit = int(os.environ.get("LLM_CHROMA_QUERY_LIMIT", "3"))
    return ChromaKnowledgeStore(
        knowledge_path,
        chroma_dir=_chroma_dir(),
        max_results=query_limit,
    )


def create_knowledge_store(path: str | None = None) -> KnowledgeStore:
    stores: list[KnowledgeStore] = []

    knowledge_path = (path or os.environ.get("LLM_KNOWLEDGE_PATH", "")).strip()
    if knowledge_path:
        stores.append(_create_static_knowledge_store(knowledge_path))

    if _env_bool("LLM_MEMORY_FROM_DB", True):
        stores.append(_create_summary_store())

    if not stores:
        return EmptyKnowledgeStore()
    if len(stores) == 1:
        return stores[0]
    return CompositeKnowledgeStore(stores)


def preload_knowledge_store(store: KnowledgeStore) -> None:
    """程序啟動時預載知識庫；重複呼叫應為 no-op。"""
    preload = getattr(store, "preload", None)
    if callable(preload):
        preload()
