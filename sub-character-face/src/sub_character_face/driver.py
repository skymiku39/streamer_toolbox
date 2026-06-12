from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ExpressionDriver(Protocol):
    @property
    def name(self) -> str:
        """Driver 識別名稱（寫入 expression.ready.driver）。"""

    def apply(self, parameters: dict[str, float]) -> dict[str, float]:
        """套用參數至外部表情系統，回傳實際生效值。"""


class VtsExpressionDriver:
    """VTube Studio 表情驅動（目前為 pass-through，可擴充 WebSocket API）。"""

    @property
    def name(self) -> str:
        return "vts"

    def apply(self, parameters: dict[str, float]) -> dict[str, float]:
        return dict(parameters)


def build_driver(driver_name: str) -> ExpressionDriver:
    if driver_name == "vts":
        return VtsExpressionDriver()
    raise ValueError(f"unsupported driver: {driver_name}")
