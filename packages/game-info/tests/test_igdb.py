from game_info.igdb import _parse_game_row


def test_parse_game_row_maps_fields() -> None:
    info = _parse_game_row(
        {
            "name": "Bad North",
            "summary": "Viking tactics game.",
            "aggregated_rating": 81.2,
            "total_rating": 70.0,
            "first_release_date": 1514764800,
            "genres": [{"name": "Strategy"}, {"name": "Indie"}],
            "platforms": [{"name": "PC (Microsoft Windows)"}],
        }
    )
    assert info is not None
    assert info.name == "Bad North"
    assert info.critic_score == 81.2
    assert info.user_score == 70.0
    assert info.genres == ("Strategy", "Indie")
    assert info.release_year == 2018


def test_parse_game_row_returns_none_without_name() -> None:
    assert _parse_game_row({"summary": "no name"}) is None
