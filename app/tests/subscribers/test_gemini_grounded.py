from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

from sub_llm.ask_response import AskResponse
from sub_llm.gemini_grounded import GeminiGroundedLlmClient


def _structured_gemini_response(*, reply: str) -> bytes:
    return json.dumps(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "reply": reply,
                                        "store_worthy": False,
                                        "memory_value": 1,
                                        "memory_note": "",
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        ]
                    }
                }
            ]
        }
    ).encode("utf-8")


def test_gemini_grounded_ask_uses_google_search_tool(monkeypatch) -> None:
    monkeypatch.setenv("QA_MEMORY_MODE", "structured")
    monkeypatch.setenv("LLM_WEB_SEARCH", "true")
    client = GeminiGroundedLlmClient(
        api_key="test-key",
        model="gemini-2.5-flash",
        system_prompt="system",
    )
    response_body = _structured_gemini_response(reply="蒜頭王八是台菜料理。")
    mock_response = MagicMock()
    mock_response.read.return_value = response_body
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_response) as urlopen:
        result = client.ask(
            "蒜頭王八是什麼",
            context="【直播狀態】直播中",
            knowledge="",
            game_reference="",
        )

    assert result.reply == "蒜頭王八是台菜料理。"
    request = urlopen.call_args.args[0]
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["tools"] == [{"google_search": {}}]
    assert "responseMimeType" not in payload["generationConfig"]
    assert "蒜頭王八" in payload["contents"][0]["parts"][0]["text"]


def test_gemini_grounded_ask_falls_back_on_grounding_error(monkeypatch) -> None:
    monkeypatch.setenv("LLM_WEB_SEARCH", "true")
    client = GeminiGroundedLlmClient(
        api_key="test-key",
        model="gemini-2.5-flash",
        system_prompt="system",
    )
    fallback_response = AskResponse(reply="備用 chat 回覆")
    error = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        code=500,
        msg="error",
        hdrs=None,
        fp=MagicMock(read=MagicMock(return_value=b"grounding failed")),
    )

    with patch("urllib.request.urlopen", side_effect=error):
        with patch.object(client._fallback, "ask", return_value=fallback_response) as fallback_ask:
            result = client.ask(
                "蒜頭王八是什麼",
                context="【直播狀態】直播中",
                knowledge="",
                game_reference="",
            )

    assert result.reply == "備用 chat 回覆"
    fallback_ask.assert_called_once_with(
        "蒜頭王八是什麼",
        context="【直播狀態】直播中",
        knowledge="",
        game_reference="",
        session_recap_reference="",
    )


def test_gemini_grounded_ask_auto_skips_grounding_without_signal(monkeypatch) -> None:
    monkeypatch.setenv("LLM_WEB_SEARCH", "auto")
    client = GeminiGroundedLlmClient(
        api_key="test-key",
        model="gemini-2.5-flash",
        system_prompt="system",
    )
    fallback_response = AskResponse(reply="一般回覆")

    with patch("urllib.request.urlopen") as urlopen:
        with patch.object(client._fallback, "ask", return_value=fallback_response) as fallback_ask:
            result = client.ask(
                "你喜歡什麼顏色",
                context="【直播狀態】直播中",
                knowledge="",
                game_reference="",
            )

    assert result.reply == "一般回覆"
    urlopen.assert_not_called()
    fallback_ask.assert_called_once()
