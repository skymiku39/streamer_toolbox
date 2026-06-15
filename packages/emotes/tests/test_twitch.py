from __future__ import annotations

from emotes.registry import EmoteRegistry
from emotes.twitch import parse_irc_emotes_tag, twitch_emote_cdn_url


def test_twitch_emote_cdn_url_static() -> None:
    url = twitch_emote_cdn_url("25")
    assert url == "https://static-cdn.jtvnw.net/emoticons/v2/25/static/dark/2.0"


def test_twitch_emote_cdn_url_animated() -> None:
    url = twitch_emote_cdn_url("42", animated=True)
    assert "/animated/" in url


def test_parse_irc_emotes_tag_single_emote() -> None:
    message = "Hello Kappa world"
    tag = "25:6-10"
    result = parse_irc_emotes_tag(tag, message)
    assert result == {
        "Kappa": "https://static-cdn.jtvnw.net/emoticons/v2/25/static/dark/2.0",
    }


def test_parse_irc_emotes_tag_multiple_positions() -> None:
    message = "Kappa Kappa"
    tag = "25:0-4,6-10"
    result = parse_irc_emotes_tag(tag, message)
    assert result["Kappa"].endswith("/static/dark/2.0")
    assert len(result) == 1


def test_parse_irc_emotes_tag_multiple_emotes() -> None:
    message = "Kappa PogChamp"
    tag = "25:0-4/1902:6-13"
    result = parse_irc_emotes_tag(tag, message)
    assert "Kappa" in result
    assert "PogChamp" in result


def test_parse_irc_emotes_tag_empty() -> None:
    assert parse_irc_emotes_tag("", "hello") == {}
    assert parse_irc_emotes_tag("25:0-4", "") == {}


def test_emote_registry_enrich_native_wins() -> None:
    registry = EmoteRegistry({"PepeLaugh": "https://cdn.example/pepe.png"})
    native = {"PepeLaugh": "https://static-cdn.jtvnw.net/emoticons/v2/1/static/dark/2.0"}
    merged = registry.enrich("PepeLaugh hello", native)
    assert merged["PepeLaugh"] == native["PepeLaugh"]


def test_emote_registry_enrich_third_party_token() -> None:
    registry = EmoteRegistry({"PepeLaugh": "https://cdn.example/pepe.png"})
    merged = registry.enrich("hello PepeLaugh", {})
    assert merged["PepeLaugh"] == "https://cdn.example/pepe.png"


def test_emote_registry_skips_absent_token() -> None:
    registry = EmoteRegistry({"PepeLaugh": "https://cdn.example/pepe.png"})
    merged = registry.enrich("hello world", {})
    assert "PepeLaugh" not in merged
