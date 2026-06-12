from pkg_events import TOPIC_CHAT_MESSAGE, ChatMessageEvent

from sub_show_overlay.model import (
    OverlaySegment,
    chat_message_to_overlay_line,
    chat_payload_to_overlay_line,
    emote_assets_from_line,
    normalize_badges,
)


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_CHAT_MESSAGE,
        "platform": "twitch",
        "message_id": "abc123",
        "author_name": "觀眾暱稱",
        "content": "hello Kappa world",
        "timestamp": "2026-06-12T17:00:00+08:00",
        "channel": "channel_name",
        "badges": [{"name": "subscriber", "version": "12"}],
        "emote_url_map": {"Kappa": "https://static-cdn.jtvnw.net/emoticons/v2/25/default/dark/1.0"},
        "reply": {"parent_user": "host", "parent_body": "welcome"},
        "raw": {},
    }


def test_chat_payload_to_overlay_line() -> None:
    line = chat_payload_to_overlay_line(_sample_payload())
    assert line.author_name == "觀眾暱稱"
    assert line.content == "hello Kappa world"
    assert line.plain_text == "觀眾暱稱: hello Kappa world"
    assert line.badges == [{"set_id": "subscriber", "id": "12"}]
    assert line.reply == {"parent_user": "host", "parent_body": "welcome"}
    assert any(segment.type == "emote" and segment.token == "Kappa" for segment in line.segments)


def test_normalize_badges_set_id_format() -> None:
    badges = normalize_badges([{"set_id": "moderator", "id": "1"}])
    assert badges == [{"set_id": "moderator", "id": "1"}]


def test_emote_assets_from_line_filters_unsafe_urls() -> None:
    event = ChatMessageEvent.from_dict(_sample_payload())
    line = chat_message_to_overlay_line(event)
    assets = emote_assets_from_line(line)
    assert assets["Kappa"].startswith("https://")

    line.segments.append(OverlaySegment(type="emote", token="bad", image_url="javascript:alert(1)"))
    assert "bad" not in emote_assets_from_line(line)


def test_overlay_entry_round_trip_fields() -> None:
    line = chat_payload_to_overlay_line(_sample_payload())
    entry = line.to_entry()
    assert entry["message_id"] == "abc123"
    assert entry["platform"] == "twitch"
    assert entry["author_name"] == "觀眾暱稱"
    assert entry["segments"]
