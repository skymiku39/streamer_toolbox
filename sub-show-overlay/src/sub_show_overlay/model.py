from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from pkg_events import ChatMessageEvent

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


@dataclass(frozen=True)
class OverlaySegment:
    type: str
    text: str = ""
    url: str = ""
    token: str = ""
    image_url: str = ""

    def to_dict(self) -> dict[str, str]:
        payload: dict[str, str] = {"type": self.type}
        if self.text:
            payload["text"] = self.text
        if self.url:
            payload["url"] = self.url
        if self.token:
            payload["token"] = self.token
        if self.image_url:
            payload["image_url"] = self.image_url
        return payload


@dataclass
class OverlayLine:
    message_id: str
    author_name: str
    content: str
    platform: str
    plain_text: str
    segments: list[OverlaySegment] = field(default_factory=list)
    badges: list[dict[str, str]] = field(default_factory=list)
    reply: dict[str, str] | None = None
    moderation_state: str = "visible"

    def to_entry(self) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "message_id": self.message_id,
            "plain_text": self.plain_text,
            "platform": self.platform,
            "segments": [segment.to_dict() for segment in self.segments],
            "moderation_state": self.moderation_state,
            "author_name": self.author_name,
            "content": self.content,
        }
        if self.badges:
            entry["badges"] = [dict(badge) for badge in self.badges]
        if self.reply:
            entry["reply"] = dict(self.reply)
        return entry


def normalize_badges(raw_badges: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for badge in raw_badges:
        if not isinstance(badge, dict):
            continue
        if "set_id" in badge or "id" in badge:
            normalized.append(
                {
                    "set_id": str(badge.get("set_id", badge.get("name", ""))),
                    "id": str(badge.get("id", badge.get("version", "1"))),
                }
            )
            continue
        if "name" in badge:
            normalized.append(
                {
                    "set_id": str(badge.get("name", "")).strip(),
                    "id": str(badge.get("version", "1")).strip() or "1",
                }
            )
            continue
        badge_type = str(badge.get("type", "")).strip()
        if badge_type:
            normalized.append({"set_id": badge_type, "id": "1"})
    return normalized


def _build_emote_pattern(emote_url_map: dict[str, str]) -> re.Pattern[str] | None:
    tokens = sorted((token for token in emote_url_map if token.strip()), key=len, reverse=True)
    if not tokens:
        return None
    return re.compile(rf"(?<!\S)({'|'.join(re.escape(token) for token in tokens)})(?!\S)")


def _segments_for_text(
    text: str,
    emote_url_map: dict[str, str],
    emote_pattern: re.Pattern[str] | None,
) -> list[OverlaySegment]:
    if not text:
        return []

    segments: list[OverlaySegment] = []
    last_idx = 0
    for match in URL_PATTERN.finditer(text):
        start, end = match.span()
        segments.extend(
            _segments_for_emotes(text[last_idx:start], emote_url_map, emote_pattern)
        )
        url = match.group(0)
        segments.append(OverlaySegment(type="link", text=url, url=url))
        last_idx = end
    segments.extend(_segments_for_emotes(text[last_idx:], emote_url_map, emote_pattern))
    return segments


def _segments_for_emotes(
    text: str,
    emote_url_map: dict[str, str],
    emote_pattern: re.Pattern[str] | None,
) -> list[OverlaySegment]:
    if not text:
        return []
    if emote_pattern is None:
        return [OverlaySegment(type="text", text=text)]

    segments: list[OverlaySegment] = []
    last_idx = 0
    for match in emote_pattern.finditer(text):
        start, end = match.span()
        if start > last_idx:
            segments.append(OverlaySegment(type="text", text=text[last_idx:start]))
        token = match.group(1)
        segments.append(
            OverlaySegment(
                type="emote",
                token=token,
                text=token,
                image_url=emote_url_map.get(token, ""),
            )
        )
        last_idx = end
    if last_idx < len(text):
        segments.append(OverlaySegment(type="text", text=text[last_idx:]))
    return segments


def _normalize_reply(reply: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(reply, dict):
        return None
    parent_user = str(reply.get("parent_user", reply.get("author_name", ""))).strip()
    parent_body = str(reply.get("parent_body", reply.get("content", ""))).strip()
    if not parent_user and not parent_body:
        return None
    return {"parent_user": parent_user, "parent_body": parent_body}


def chat_message_to_overlay_line(event: ChatMessageEvent) -> OverlayLine:
    emote_pattern = _build_emote_pattern(event.emote_url_map)
    segments = _segments_for_text(event.content, event.emote_url_map, emote_pattern)
    author = event.author_name.strip()
    plain_text = f"{author}: {event.content}" if author else event.content
    return OverlayLine(
        message_id=event.message_id,
        author_name=author,
        content=event.content,
        platform=event.platform,
        plain_text=plain_text,
        segments=segments,
        badges=normalize_badges(event.badges),
        reply=_normalize_reply(event.reply),
    )


def chat_payload_to_overlay_line(payload: dict[str, Any]) -> OverlayLine:
    return chat_message_to_overlay_line(ChatMessageEvent.from_dict(payload))


def emote_assets_from_line(line: OverlayLine) -> dict[str, str]:
    assets: dict[str, str] = {}
    for segment in line.segments:
        if segment.type != "emote":
            continue
        key = segment.token or segment.text
        if key and segment.image_url and _is_safe_url(segment.image_url):
            assets[key] = segment.image_url
    return assets


def _is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
