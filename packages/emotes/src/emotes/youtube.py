from __future__ import annotations

from typing import Any


def _thumbnail_url(node: dict[str, Any]) -> str:
    thumbnails = node.get("thumbnails")
    if not isinstance(thumbnails, list):
        return ""
    for item in thumbnails:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if url:
            return url
    return ""


def _emoji_tokens(emoji_node: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    shortcuts = emoji_node.get("shortcuts")
    if isinstance(shortcuts, list):
        for shortcut in shortcuts:
            text = str(shortcut).strip()
            if text:
                tokens.append(text)
    emoji_id = str(emoji_node.get("emojiId", "")).strip()
    if emoji_id:
        tokens.append(emoji_id)
    image = emoji_node.get("image")
    if isinstance(image, dict):
        accessibility = image.get("accessibility")
        if isinstance(accessibility, dict):
            data = accessibility.get("accessibilityData")
            if isinstance(data, dict):
                alt = str(data.get("label", "")).strip()
                if alt:
                    tokens.append(alt)
    return tokens


def _collect_from_runs(runs: list[Any], result: dict[str, str]) -> None:
    for run in runs:
        if not isinstance(run, dict):
            continue
        emoji = run.get("emoji")
        if isinstance(emoji, dict):
            image = emoji.get("image")
            url = _thumbnail_url(image) if isinstance(image, dict) else ""
            if url:
                for token in _emoji_tokens(emoji):
                    result.setdefault(token, url)


def _collect_sticker(raw: dict[str, Any], result: dict[str, str]) -> None:
    sticker = raw.get("sticker")
    if not isinstance(sticker, dict):
        return
    url = _thumbnail_url(sticker)
    if not url:
        return
    alt = ""
    accessibility = sticker.get("accessibility")
    if isinstance(accessibility, dict):
        data = accessibility.get("accessibilityData")
        if isinstance(data, dict):
            alt = str(data.get("label", "")).strip()
    token = alt or "[Super Sticker]"
    result.setdefault(token, url)


def build_youtube_emote_url_map(raw: dict[str, Any], _message_text: str = "") -> dict[str, str]:
    """Extract YouTube custom emoji / sticker image URLs from pytchat raw payload."""
    if not isinstance(raw, dict):
        return {}

    result: dict[str, str] = {}
    message = raw.get("message")
    if isinstance(message, dict):
        runs = message.get("runs")
        if isinstance(runs, list):
            _collect_from_runs(runs, result)

    _collect_sticker(raw, result)

    action = raw.get("actionType")
    if isinstance(action, dict):
        _collect_sticker(action, result)

    return result
