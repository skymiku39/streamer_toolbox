from __future__ import annotations

import os

from stream_store import StreamTextStore

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
        return OpenAiCompatibleLlmClient.from_env()
    raise ValueError(f"unsupported LLM_BACKEND: {selected!r}")


def _create_summary_store() -> SummaryKnowledgeStore:
    db_path = os.environ.get("STREAM_DB_PATH", "data/stream_text.db")
    session_id = (os.environ.get("STREAM_SESSION_ID") or "").strip() or None
    limit = int(os.environ.get("LLM_MEMORY_SUMMARY_LIMIT", "10"))
    store = StreamTextStore(db_path)
    return SummaryKnowledgeStore(store, session_id, limit=limit)


def create_knowledge_store(path: str | None = None) -> KnowledgeStore:
    stores: list[KnowledgeStore] = []
    if _env_bool("LLM_MEMORY_FROM_DB", True):
        stores.append(_create_summary_store())

    knowledge_path = (path or os.environ.get("LLM_KNOWLEDGE_PATH", "")).strip()
    if knowledge_path:
        stores.append(FileKnowledgeStore(knowledge_path))

    if not stores:
        return EmptyKnowledgeStore()
    if len(stores) == 1:
        return stores[0]
    return CompositeKnowledgeStore(stores)
