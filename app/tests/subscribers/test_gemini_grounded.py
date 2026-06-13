from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from sub_llm.gemini_grounded import GeminiGroundedLlmClient


def test_gemini_grounded_ask_uses_google_search_tool() -> None:
    client = GeminiGroundedLlmClient(
        api_key="test-key",
        model="gemini-2.5-flash",
        system_prompt="system",
    )
    response_body = json.dumps(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    "這段還沒聊過蒜頭王八。"
                                    "若你指的是把王八和蒜頭一起燉的台菜，"
                                    "那是用王八（鱉）加蒜頭、九層塔等去燉的料理。"
                                )
                            }
                        ]
                    }
                }
            ]
        }
    ).encode("utf-8")
    mock_response = MagicMock()
    mock_response.read.return_value = response_body
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_response) as urlopen:
        reply = client.ask(
            "蒜頭王八是什麼",
            context="【直播狀態】直播中",
            knowledge="",
            game_reference="",
        )

    assert "蒜頭" in reply or "王八" in reply or "燉" in reply
    request = urlopen.call_args.args[0]
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["tools"] == [{"google_search": {}}]
    assert "蒜頭王八" in payload["contents"][0]["parts"][0]["text"]
