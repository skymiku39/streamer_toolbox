from __future__ import annotations

import os

from stream_store import StreamTextStore

from sub_llm.chroma_store import ChromaKnowledgeStore, ChromaSummaryKnowledgeStore
from sub_llm.debug_agent_log import agent_log
from sub_llm.knowledge import (
    CompositeKnowledgeStore,
    EmptyKnowledgeStore,
    FileKnowledgeStore,
    KnowledgeStore,
    SummaryKnowledgeStore,
)
from sub_llm.llm import LlmClient, TemplateLlmClient
from sub_llm.openai_client import OpenAiCompatibleLlmClient


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def create_llm_client(backend: str | None = None) -> LlmClient:
    selected = (backend or os.environ.get("LLM_BACKEND", "template") or "template").lower()
    if selected == "template":
        return TemplateLlmClient()
    if selected in {"openai", "gemini"}:
        return OpenAiCompatibleLlmClient.from_env(backend=selected)
    raise ValueError(f"unsupported LLM_BACKEND: {selected!r}")


def _create_summary_store() -> KnowledgeStore:
    db_path = os.environ.get("STREAM_DB_PATH", "data/stream_text.db")
    session_id = (os.environ.get("STREAM_SESSION_ID") or "").strip() or None
    limit = int(os.environ.get("LLM_MEMORY_SUMMARY_LIMIT", "10"))
    store = StreamTextStore(db_path)
    backend = (os.environ.get("LLM_KNOWLEDGE_BACKEND", "file") or "file").strip().lower()
    if backend == "chroma":
        chroma_dir = (os.environ.get("LLM_CHROMA_DIR", "data/chroma") or "data/chroma").strip()
        memory_query_limit = int(os.environ.get("LLM_CHROMA_MEMORY_QUERY_LIMIT", "5"))
        return ChromaSummaryKnowledgeStore(
            store,
            session_id,
            chroma_dir=chroma_dir,
            limit=limit,
            max_results=memory_query_limit,
        )
    return SummaryKnowledgeStore(store, session_id, limit=limit)


def _create_static_knowledge_store(knowledge_path: str) -> KnowledgeStore:
    backend = (os.environ.get("LLM_KNOWLEDGE_BACKEND", "file") or "file").strip().lower()
    if backend == "chroma":
        chroma_dir = (os.environ.get("LLM_CHROMA_DIR", "data/chroma") or "data/chroma").strip()
        query_limit = int(os.environ.get("LLM_CHROMA_QUERY_LIMIT", "3"))
        return ChromaKnowledgeStore(
            knowledge_path,
            chroma_dir=chroma_dir,
            max_results=query_limit,
        )
    if backend == "file":
        return FileKnowledgeStore(knowledge_path)
    raise ValueError(f"unsupported LLM_KNOWLEDGE_BACKEND: {backend!r}")


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
        result = stores[0]
    else:
        result = CompositeKnowledgeStore(stores)

    # region agent log
    agent_log(
        hypothesis_id="H1",
        location="factory.py:create_knowledge_store",
        message="knowledge store created",
        data={
            "backend": os.environ.get("LLM_KNOWLEDGE_BACKEND", "file"),
            "knowledge_path": knowledge_path,
            "memory_from_db": _env_bool("LLM_MEMORY_FROM_DB", True),
            "store_type": type(result).__name__,
            "child_types": [type(s).__name__ for s in getattr(result, "_stores", [result])],
        },
    )
    # endregion
    return result


def preload_knowledge_store(store: KnowledgeStore) -> None:
    """程序啟動時預載知識庫；重複呼叫應為 no-op。"""
    preload = getattr(store, "preload", None)
    if callable(preload):
        preload()
        # region agent log
        agent_log(
            hypothesis_id="H5",
            location="factory.py:preload_knowledge_store",
            message="preload completed",
            data={"store_type": type(store).__name__},
        )
        # endregion
