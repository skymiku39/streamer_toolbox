from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from sub_llm.ask_response import AskResponse
from sub_llm.hybrid_client import HybridGeminiLlmClient, _parse_agent_decision
from sub_llm.openai_client import LlmApiError, OpenAiCompatibleLlmClient
from sub_llm.short_term_rag import SHORT_TERM_MARKER


def _client() -> tuple[HybridGeminiLlmClient, OpenAiCompatibleLlmClient, OpenAiCompatibleLlmClient]:
    agent = OpenAiCompatibleLlmClient(base_url="https://x/v1", api_key="k", model="lite")
    main = OpenAiCompatibleLlmClient(base_url="https://x/v1", api_key="k", model="flash")
    return HybridGeminiLlmClient(agent_client=agent, main_client=main), agent, main


def _memory_knowledge() -> str:
    return f"{SHORT_TERM_MARKER}\n1. 問：今天玩什麼\n   答：在玩 DND"


def test_ask_without_short_term_memory_escalates_to_main() -> None:
    client, agent, main = _client()
    agent.complete = MagicMock()
    main.ask = MagicMock(return_value=AskResponse(reply="main answer"))

    result = client.ask("問題", context="", knowledge="一般知識，無近期問答")

    assert result.reply == "main answer"
    agent.complete.assert_not_called()
    main.ask.assert_called_once()


def test_ask_with_memory_agent_answers_without_escalation() -> None:
    client, agent, main = _client()
    agent.complete = MagicMock(
        return_value=json.dumps({"action": "answer", "reply": "來自記憶的回覆"})
    )
    main.ask = MagicMock()

    result = client.ask("今天玩什麼", context="", knowledge=_memory_knowledge())

    assert result.reply == "來自記憶的回覆"
    agent.complete.assert_called_once()
    main.ask.assert_not_called()


def test_ask_with_memory_agent_escalates_when_insufficient() -> None:
    client, agent, main = _client()
    agent.complete = MagicMock(
        return_value=json.dumps({"action": "escalate", "reply": ""})
    )
    main.ask = MagicMock(return_value=AskResponse(reply="main answer"))

    result = client.ask("問題", context="ctx", knowledge=_memory_knowledge())

    assert result.reply == "main answer"
    main.ask.assert_called_once()


def test_ask_falls_back_to_main_when_agent_fails() -> None:
    client, agent, main = _client()
    agent.complete = MagicMock(side_effect=LlmApiError("boom"))
    main.ask = MagicMock(return_value=AskResponse(reply="main answer"))

    result = client.ask("問題", context="", knowledge=_memory_knowledge())

    assert result.reply == "main answer"
    main.ask.assert_called_once()


def test_parse_agent_decision_strips_json_fence() -> None:
    action, reply = _parse_agent_decision('```json\n{"action":"answer","reply":"hi"}\n```')
    assert action == "answer"
    assert reply == "hi"


def test_parse_agent_decision_defaults_to_escalate_on_invalid() -> None:
    action, reply = _parse_agent_decision("not json")
    assert action == "escalate"
    assert reply == ""


def test_from_env_builds_lite_and_main_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "key")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("GOOGLE_AI_MODEL", raising=False)
    monkeypatch.delenv("LLM_AGENT_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_BASE", raising=False)

    client = HybridGeminiLlmClient.from_env()

    assert client._agent._model == "gemini-2.0-flash-lite"
    assert client._main._model == "gemini-2.5-flash"


def test_from_env_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LLM_API_KEY",
        "GOOGLE_AI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="API_KEY"):
        HybridGeminiLlmClient.from_env()
