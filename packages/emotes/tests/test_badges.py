from __future__ import annotations

from emotes.badges import parse_badge_response


def test_parse_badge_response() -> None:
    response = {
        "data": [
            {
                "set_id": "subscriber",
                "versions": [
                    {
                        "id": "12",
                        "image_url_1x": "https://example.com/sub1.png",
                        "image_url_2x": "https://example.com/sub2.png",
                    }
                ],
            }
        ]
    }
    result = parse_badge_response(response)
    assert result == {"subscriber/12": "https://example.com/sub2.png"}
