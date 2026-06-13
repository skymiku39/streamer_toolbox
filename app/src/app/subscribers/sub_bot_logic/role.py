from __future__ import annotations

from typing import Any


def resolve_role(badges: list[Any] | None) -> str:
    """由 chat.message badges 推斷觀眾角色（Twitch / ttv_chat 格式）。"""
    names: set[str] = set()
    for badge in badges or []:
        if not isinstance(badge, dict):
            continue
        if badge.get("name"):
            names.add(str(badge["name"]).lower())
        if badge.get("set_id"):
            names.add(str(badge["set_id"]).lower())
    if "broadcaster" in names:
        return "broadcaster"
    if "moderator" in names:
        return "mod"
    if "vip" in names:
        return "vip"
    if "subscriber" in names or "founder" in names:
        return "subscriber"
    return "viewer"
