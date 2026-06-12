from __future__ import annotations

import os

from sub_llm.knowledge import EmptyKnowledgeStore, FileKnowledgeStore, KnowledgeStore
from sub_llm.llm import LlmClient, TemplateLlmClient
from sub_llm.openai_client import OpenAiCompatibleLlmClient


def create_llm_client(backend: str | None = None) -> LlmClient:
    selected = (backend or os.environ.get("LLM_BACKEND", "template") or "template").lower()
    if selected == "template":
        return TemplateLlmClient()
    if selected in {"openai", "gemini"}:
        return OpenAiCompatibleLlmClient.from_env()
    raise ValueError(f"unsupported LLM_BACKEND: {selected!r}")


def create_knowledge_store(path: str | None = None) -> KnowledgeStore:
    knowledge_path = (path or os.environ.get("LLM_KNOWLEDGE_PATH", "")).strip()
    if not knowledge_path:
        return EmptyKnowledgeStore()
    return FileKnowledgeStore(knowledge_path)
