from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

from sub_character_face.vts_ws import VtsWebSocketClient

logger = logging.getLogger(__name__)


@runtime_checkable
class ExpressionDriver(Protocol):
    @property
    def name(self) -> str:
        """Driver 識別名稱（寫入 expression.ready.driver）。"""

    def apply(self, parameters: dict[str, float]) -> dict[str, float]:
        """套用參數至外部表情系統，回傳實際生效值。"""


class VtsPassthroughDriver:
    """離線／測試用 pass-through，不連線 VTS。"""

    @property
    def name(self) -> str:
        return "vts"

    def apply(self, parameters: dict[str, float]) -> dict[str, float]:
        return dict(parameters)


# 向後相容測試別名
VtsExpressionDriver = VtsPassthroughDriver


class VtsWebSocketDriver:
    def __init__(self, client: VtsWebSocketClient) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return "vts"

    def apply(self, parameters: dict[str, float]) -> dict[str, float]:
        try:
            self._client.inject_parameters(parameters)
        except Exception as exc:
            logger.warning("VTS inject failed, using mapped values only: %s", exc)
        return dict(parameters)


def build_driver(driver_name: str) -> ExpressionDriver:
    if driver_name == "vts-stub":
        return VtsPassthroughDriver()
    if driver_name == "vts":
        client = VtsWebSocketClient(
            url=os.environ.get("VTS_WS_URL", "ws://localhost:8001"),
            plugin_name=os.environ.get("VTS_PLUGIN_NAME", "Streamer Toolbox"),
            plugin_developer=os.environ.get("VTS_PLUGIN_DEVELOPER", "streamer-toolbox"),
            auth_token=os.environ.get("VTS_AUTH_TOKEN", ""),
        )
        return VtsWebSocketDriver(client)
    raise ValueError(f"unsupported driver: {driver_name}")
