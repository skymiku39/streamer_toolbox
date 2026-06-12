from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class VtsWebSocketClient:
    """VTube Studio Public API 最小 WebSocket 客戶端（InjectParameterData）。"""

    def __init__(
        self,
        *,
        url: str,
        plugin_name: str,
        plugin_developer: str,
        auth_token: str = "",
        timeout_sec: float = 3.0,
    ) -> None:
        self._url = url
        self._plugin_name = plugin_name
        self._plugin_developer = plugin_developer
        self._auth_token = auth_token
        self._timeout_sec = timeout_sec

    def inject_parameters(self, parameters: dict[str, float]) -> None:
        import websockets.sync.client

        parameter_values = [
            {"id": name, "value": float(value), "weight": 1.0}
            for name, value in parameters.items()
        ]
        with websockets.sync.client.connect(self._url, open_timeout=self._timeout_sec) as ws:
            self._authenticate(ws)
            request = {
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": str(uuid.uuid4()),
                "messageType": "InjectParameterDataRequest",
                "data": {
                    "faceFound": False,
                    "mode": "set",
                    "parameterValues": parameter_values,
                },
            }
            ws.send(json.dumps(request))
            raw = ws.recv(timeout=self._timeout_sec)
            response = json.loads(raw)
            if response.get("messageType") == "APIError":
                raise RuntimeError(str(response.get("data", response)))

    def _authenticate(self, ws: Any) -> None:
        request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": str(uuid.uuid4()),
            "messageType": "AuthenticationTokenRequest",
            "data": {
                "pluginName": self._plugin_name,
                "pluginDeveloper": self._plugin_developer,
                "pluginIcon": "",
                "authenticationToken": self._auth_token,
            },
        }
        ws.send(json.dumps(request))
        raw = ws.recv(timeout=self._timeout_sec)
        response = json.loads(raw)
        message_type = response.get("messageType")
        if message_type == "AuthenticationTokenResponse":
            data = response.get("data", {})
            if not data.get("authenticated"):
                raise RuntimeError("VTS authentication was not approved")
            return
        if message_type == "APIError":
            raise RuntimeError(str(response.get("data", response)))
        logger.warning("unexpected VTS auth response: %s", message_type)
