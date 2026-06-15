from __future__ import annotations

from emotes.youtube import build_youtube_emote_url_map


def test_build_youtube_emote_url_map_from_runs() -> None:
    raw = {
        "message": {
            "runs": [
                {"text": "hello "},
                {
                    "emoji": {
                        "emojiId": "emoji-1",
                        "shortcuts": [":wave:"],
                        "image": {
                            "thumbnails": [{"url": "https://example.com/emoji.png"}],
                        },
                    }
                },
            ]
        }
    }
    result = build_youtube_emote_url_map(raw, "hello :wave:")
    assert result[":wave:"] == "https://example.com/emoji.png"
    assert result["emoji-1"] == "https://example.com/emoji.png"


def test_build_youtube_emote_url_map_super_sticker() -> None:
    raw = {
        "sticker": {
            "thumbnails": [{"url": "https://example.com/sticker.png"}],
            "accessibility": {"accessibilityData": {"label": "Cool Sticker"}},
        }
    }
    result = build_youtube_emote_url_map(raw)
    assert result["Cool Sticker"] == "https://example.com/sticker.png"
