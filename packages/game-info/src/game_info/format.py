from __future__ import annotations

from game_info.models import GameReviewInfo

_INTRA_SEP = "·"


def format_game_info_for_prompt(info: GameReviewInfo) -> str:
    """將遊戲資料格式化為精簡單行 prompt 片段。"""
    parts = [info.name]
    if info.genres:
        parts.append("/".join(info.genres))
    if info.platforms:
        parts.append("/".join(info.platforms[:3]))
    if info.release_year is not None:
        parts.append(str(info.release_year))
    score_parts: list[str] = []
    if info.critic_score is not None:
        score_parts.append(f"媒體{info.critic_score:.0f}")
    if info.user_score is not None:
        score_parts.append(f"玩家{info.user_score:.0f}")
    if score_parts:
        parts.append("/".join(score_parts))
    if info.summary.strip():
        summary = info.summary.strip().replace("\n", " ")
        if len(summary) > 200:
            summary = summary[:197] + "..."
        parts.append(summary)
    parts.append(f"來源:{info.source}")
    return f"遊戲:{_INTRA_SEP.join(parts)}"
