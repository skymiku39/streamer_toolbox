"""Twitch OAuth scope 定義（對齊 toolbox EventSub + connector 需求）。"""

from __future__ import annotations

from identity_oauth.protocol import AccountRole

BOT_SCOPES: tuple[str, ...] = (
    "chat:read",
    "chat:edit",
    "user:read:chat",
    "user:write:chat",
    "user:read:emotes",
    "moderator:read:followers",
    "moderator:manage:chat_messages",
    "moderator:manage:banned_users",
    "moderator:manage:automod",
)

CHANNEL_SCOPES: tuple[str, ...] = (
    "channel:read:subscriptions",
    "channel:read:redemptions",
    "bits:read",
    "channel:moderate",
    "clips:edit",
    "channel:read:polls",
    "channel:read:predictions",
    "channel:read:hype_train",
    "user:write:chat",
    "user:read:emotes",
)

ALL_SCOPES: tuple[str, ...] = tuple(dict.fromkeys([*BOT_SCOPES, *CHANNEL_SCOPES]))


def scopes_for_role(role: AccountRole, *, single_account: bool) -> list[str]:
    if single_account:
        return list(ALL_SCOPES)
    if role == "bot":
        return list(BOT_SCOPES)
    return list(CHANNEL_SCOPES)
