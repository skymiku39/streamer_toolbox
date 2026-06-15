from __future__ import annotations

_TWITCH_CDN = "https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/{fmt}/dark/2.0"


def twitch_emote_cdn_url(emote_id: str, *, animated: bool = False) -> str:
    emote_id = str(emote_id).strip()
    fmt = "animated" if animated else "static"
    return _TWITCH_CDN.format(emote_id=emote_id, fmt=fmt)


def parse_irc_emotes_tag(emotes_tag: str, message: str) -> dict[str, str]:
    """Parse Twitch IRC ``emotes`` tag into display token -> CDN URL map."""
    if not emotes_tag or not message:
        return {}

    result: dict[str, str] = {}
    for entry in emotes_tag.split("/"):
        if not entry or ":" not in entry:
            continue
        emote_id, positions_raw = entry.split(":", 1)
        emote_id = emote_id.strip()
        if not emote_id:
            continue
        url = twitch_emote_cdn_url(emote_id)
        for pos in positions_raw.split(","):
            pos = pos.strip()
            if "-" not in pos:
                continue
            start_s, end_s = pos.split("-", 1)
            try:
                start = int(start_s)
                end = int(end_s)
            except ValueError:
                continue
            if start < 0 or end < start or end >= len(message):
                continue
            token = message[start : end + 1]
            if token:
                result[token] = url
    return result
