from __future__ import annotations

from typing import Protocol

from game_info.models import GameReviewInfo


class GameInfoProvider(Protocol):
    def lookup(self, game_name: str) -> GameReviewInfo | None:
        """依遊戲名稱查詢評分與簡介；查無或失敗時回傳 None。"""
