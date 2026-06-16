from __future__ import annotations

from datetime import UTC, datetime

from ingress_yt_read.mapper import map_chat_message
from tubechat_lens.reader import ChatMessage


def test_map_youtube_emotes_from_raw() -> None:
    message = ChatMessage(
        message_id="yt-1",
        author_name="Viewer",
        author_id="author-1",
        message="hello :wave:",
        timestamp=datetime(2026, 6, 12, 9, 0, 0, tzinfo=UTC),
        message_type="textMessage",
        raw={
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
        },
    )
    event = map_chat_message(message, "my-channel")
    assert event.emote_url_map[":wave:"] == "https://example.com/emoji.png"
