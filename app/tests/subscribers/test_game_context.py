from sub_llm.game_context import (
    build_game_reference,
    is_playable_game_category,
    should_enrich_game_context,
)
from game_info.models import GameReviewInfo


class StubGameProvider:
    def __init__(self, info: GameReviewInfo | None) -> None:
        self._info = info
        self.queries: list[str] = []

    def lookup(self, game_name: str) -> GameReviewInfo | None:
        self.queries.append(game_name)
        return self._info


def test_should_enrich_for_playable_live_game() -> None:
    assert should_enrich_game_context("這遊戲好玩嗎", "Bad North")
    assert should_enrich_game_context("bad north 評分多少", "Bad North")
    assert should_enrich_game_context("今天天氣如何", "Bad North")
    assert not should_enrich_game_context("這遊戲好玩嗎", "Just Chatting")


def test_is_playable_game_category() -> None:
    assert is_playable_game_category("Bad North")
    assert not is_playable_game_category("Just Chatting")


def test_build_game_reference_returns_formatted_text() -> None:
    provider = StubGameProvider(
        GameReviewInfo(
            name="Bad North",
            summary="即時戰略遊戲。",
            critic_score=80.0,
            user_score=70.0,
        )
    )
    text = build_game_reference(
        "這遊戲評分多少",
        game_name="Bad North",
        provider=provider,
    )
    assert "【遊戲資料參考：Bad North】" in text
    assert provider.queries == ["Bad North"]


def test_build_game_reference_includes_for_unrelated_question() -> None:
    provider = StubGameProvider(GameReviewInfo(name="Bad North", summary="即時戰略遊戲。"))
    text = build_game_reference("LNG 是什麼", game_name="Bad North", provider=provider)
    assert "【遊戲資料參考：Bad North】" in text
    assert provider.queries == ["Bad North"]
