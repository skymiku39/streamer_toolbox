from __future__ import annotations

from unittest.mock import MagicMock, patch

from sub_character_face.driver import VtsWebSocketDriver
from sub_character_face.vts_ws import VtsWebSocketClient


def test_vts_websocket_driver_applies_parameters() -> None:
    client = MagicMock(spec=VtsWebSocketClient)
    driver = VtsWebSocketDriver(client)
    result = driver.apply({"mouth_smile": 0.8})
    client.inject_parameters.assert_called_once_with({"mouth_smile": 0.8})
    assert result["mouth_smile"] == 0.8


def test_vts_websocket_driver_returns_parameters_when_inject_fails() -> None:
    client = MagicMock(spec=VtsWebSocketClient)
    client.inject_parameters.side_effect = RuntimeError("offline")
    driver = VtsWebSocketDriver(client)
    result = driver.apply({"eye_open": 1.0})
    assert result["eye_open"] == 1.0


@patch("websockets.sync.client.connect")
def test_vts_client_sends_inject_request(mock_connect) -> None:
    ws = MagicMock()
    ws.recv.side_effect = [
        '{"messageType":"AuthenticationTokenResponse","data":{"authenticated":true}}',
        '{"messageType":"InjectParameterDataResponse","data":{}}',
    ]
    mock_connect.return_value.__enter__.return_value = ws

    client = VtsWebSocketClient(
        url="ws://localhost:8001",
        plugin_name="Test",
        plugin_developer="Dev",
        auth_token="token",
    )
    client.inject_parameters({"mouth_smile": 0.5})

    assert ws.send.call_count == 2
    inject_payload = ws.send.call_args_list[1].args[0]
    assert "InjectParameterDataRequest" in inject_payload
