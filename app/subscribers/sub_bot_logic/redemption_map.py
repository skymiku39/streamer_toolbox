"""頻道點數兌換回應（對照 twitch_api utils/redemption_responses.py）。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_FALLBACK_TEMPLATE = "🎯 {user} 兌換了「{title}」（{cost} 點）{input}"


class RedemptionResponseMap:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._map: dict[str, str] = {}
        self._default: str = _FALLBACK_TEMPLATE
        self.reload()

    def reload(self) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
        except FileNotFoundError:
            raw = {}
        except Exception as exc:
            logger.error("載入兌換回應表失敗：%s", exc)
            raw = {}

        self._default = str(raw.pop("_default", _FALLBACK_TEMPLATE))
        self._map = {
            str(key): str(value)
            for key, value in raw.items()
            if not str(key).startswith("_") and str(value).strip()
        }

    def get_response(self, reward_title: str, user: str, cost: int, user_input: str) -> str:
        template = self._map.get(reward_title, self._default)
        input_suffix = f"：{user_input}" if user_input else ""
        try:
            return template.format(
                user=user,
                title=reward_title,
                cost=cost,
                input=input_suffix,
            )
        except (KeyError, IndexError, ValueError):
            return self._default.format(
                user=user,
                title=reward_title,
                cost=cost,
                input=input_suffix,
            )
