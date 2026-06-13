from __future__ import annotations

from game_info.models import GameReviewInfo


def format_game_info_for_prompt(info: GameReviewInfo) -> str:
    """將遊戲資料格式化為 prompt 段落（純文字、適合聊天室助手）。"""
    lines = [f"【遊戲資料參考：{info.name}】"]
    if info.genres:
        lines.append(f"類型：{'、'.join(info.genres)}")
    if info.platforms:
        lines.append(f"平台：{'、'.join(info.platforms)}")
    if info.release_year is not None:
        lines.append(f"發行：{info.release_year}")
    score_parts: list[str] = []
    if info.critic_score is not None:
        score_parts.append(f"媒體評分 {info.critic_score:.0f}/100")
    if info.user_score is not None:
        score_parts.append(f"玩家評分 {info.user_score:.0f}/100")
    if score_parts:
        lines.append("評分：" + "、".join(score_parts))
    if info.summary.strip():
        summary = info.summary.strip().replace("\n", " ")
        if len(summary) > 400:
            summary = summary[:397] + "..."
        lines.append(f"簡介：{summary}")
    lines.append(f"（資料來源：{info.source}）")
    return "\n".join(lines)
