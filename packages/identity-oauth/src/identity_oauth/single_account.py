from __future__ import annotations

import os
from typing import Literal

AccountRole = Literal["channel", "bot"]
ACCOUNT_ROLES: tuple[AccountRole, ...] = ("channel", "bot")


def _env_bool(environ: dict[str, str], name: str, default: bool = False) -> bool:
    raw = (environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def read_single_account_mode(environ: dict[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return _env_bool(env, "TWITCH_SINGLE_ACCOUNT", False)


def resolve_refresh_token(environ: dict[str, str], role: AccountRole) -> str:
    legacy = (environ.get("TWITCH_REFRESH_TOKEN") or "").strip()
    if role == "channel":
        return (environ.get("TWITCH_CHANNEL_REFRESH_TOKEN") or "").strip() or legacy
    bot = (environ.get("TWITCH_BOT_REFRESH_TOKEN") or "").strip() or legacy
    if read_single_account_mode(environ):
        channel = (environ.get("TWITCH_CHANNEL_REFRESH_TOKEN") or "").strip() or legacy
        return channel or bot
    return bot


def resolve_static_access_token(environ: dict[str, str], role: AccountRole) -> str:
    legacy = (environ.get("TWITCH_ACCESS_TOKEN") or "").strip()
    if role == "channel":
        return (environ.get("TWITCH_CHANNEL_ACCESS_TOKEN") or "").strip() or legacy
    bot = (environ.get("TWITCH_BOT_ACCESS_TOKEN") or "").strip() or legacy
    if read_single_account_mode(environ):
        channel = (environ.get("TWITCH_CHANNEL_ACCESS_TOKEN") or "").strip() or legacy
        return channel or bot
    return bot
