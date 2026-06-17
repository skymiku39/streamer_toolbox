from __future__ import annotations

from game_info.format import format_game_info_for_prompt
from game_info.models import GameReviewInfo


def test_format_includes_scores_and_summary() -> None:
    text = format_game_info_for_prompt(
        GameReviewInfo(
            name="Bad North",
            summary="即時戰略遊戲，玩家指揮維京部隊防守島嶼。",
            critic_score=80.5,
            user_score=72.0,
            genres=("Strategy", "Indie"),
            platforms=("PC (Microsoft Windows)", "Nintendo Switch"),
            release_year=2018,
        )
    )
    assert "遊戲:Bad North" in text
    assert "媒體80" in text
    assert "玩家72" in text
    assert "即時戰略遊戲" in text
    assert "Strategy" in text


def test_format_truncates_long_summary() -> None:
    text = format_game_info_for_prompt(
        GameReviewInfo(
            name="Demo",
            summary="A" * 500,
        )
    )
    assert "..." in text
    assert len(text) < 600
