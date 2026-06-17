from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from sub_llm.openai_client import LlmApiError, OpenAiCompatibleLlmClient


def test_ask_logs_prompt_messages(capsys: pytest.CaptureFixture[str]) -> None:
    client = OpenAiCompatibleLlmClient(
        base_url="https://example.com/v1",
        api_key="test-key",
        model="test-model",
        system_prompt="你是直播助手",
    )
    payload = {"choices": [{"message": {"content": "這是回覆"}}]}
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(payload).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = None

    with patch("sub_llm.openai_client.urllib.request.urlopen", return_value=mock_response):
        client.ask("問題", context="逐字稿", knowledge="知識")

    err = capsys.readouterr().err
    assert "[sub-llm] llm_prompt purpose=ask" in err
    assert "你是直播助手" in err
    assert "[問題]" in err


def test_ask_returns_assistant_content() -> None:
    client = OpenAiCompatibleLlmClient(
        base_url="https://example.com/v1",
        api_key="test-key",
        model="test-model",
        system_prompt="你是直播助手",
    )
    payload = {"choices": [{"message": {"content": "這是回覆"}}]}
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(payload).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = None

    with patch("sub_llm.openai_client.urllib.request.urlopen", return_value=mock_response):
        answer = client.ask("問題", context="逐字稿", knowledge="知識")

    assert answer.reply == "這是回覆"


def test_from_env_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        OpenAiCompatibleLlmClient.from_env()


def test_ask_raises_on_http_error() -> None:
    client = OpenAiCompatibleLlmClient(
        base_url="https://example.com/v1",
        api_key="test-key",
        model="test-model",
    )
    import urllib.error

    error = urllib.error.HTTPError(
        url="https://example.com/v1/chat/completions",
        code=500,
        msg="error",
        hdrs=None,
        fp=MagicMock(read=MagicMock(return_value=b"boom")),
    )
    with patch("sub_llm.openai_client.urllib.request.urlopen", side_effect=error):
        with pytest.raises(LlmApiError, match="500"):
            client.ask("問題", context="", knowledge="")


def test_generate_startup_greeting_omits_json_mode_when_structured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QA_MEMORY_MODE", "structured")
    client = OpenAiCompatibleLlmClient(
        base_url="https://example.com/v1",
        api_key="test-key",
        model="test-model",
    )
    seen_payloads: list[dict] = []

    def fake_post(_path: str, payload: dict) -> dict:
        seen_payloads.append(payload)
        return {"choices": [{"message": {"content": "哈囉，我上線了！"}}]}

    with patch.object(client, "_post_json", side_effect=fake_post):
        greeting = client.generate_startup_greeting(
            channel="skymiku39",
            trigger_prefixes=("!ask",),
        )

    assert greeting == "哈囉，我上線了！"
    assert seen_payloads
    assert "response_format" not in seen_payloads[0]


def test_generate_startup_greeting_unwraps_json_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QA_MEMORY_MODE", "structured")
    client = OpenAiCompatibleLlmClient(
        base_url="https://example.com/v1",
        api_key="test-key",
        model="test-model",
    )
    content = json.dumps({"message": "哈囉！"}, ensure_ascii=False)

    def fake_post(_path: str, _payload: dict) -> dict:
        return {"choices": [{"message": {"content": content}}]}

    with patch.object(client, "_post_json", side_effect=fake_post):
        greeting = client.generate_startup_greeting(
            channel="skymiku39",
            trigger_prefixes=("!ask",),
        )

    assert greeting == "哈囉！"
