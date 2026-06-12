from __future__ import annotations

from sub_llm.factory import create_llm_client
from sub_llm.llm import TemplateLlmClient
from sub_llm.openai_client import OpenAiCompatibleLlmClient


def test_create_llm_client_template() -> None:
    client = create_llm_client("template")
    assert isinstance(client, TemplateLlmClient)


def test_create_llm_client_openai_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "key")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    client = create_llm_client("openai")
    assert isinstance(client, OpenAiCompatibleLlmClient)
