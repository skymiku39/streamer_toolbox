from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameReviewInfo:
    """遊戲評論網風格的精簡資料，供 LLM prompt 參考。"""

    name: str
    summary: str = ""
    critic_score: float | None = None
    user_score: float | None = None
    genres: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    release_year: int | None = None
    source: str = "igdb"
