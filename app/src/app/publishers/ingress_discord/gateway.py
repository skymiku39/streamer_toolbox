from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC
from typing import Any

import discord

from ingress_discord.mapping import DiscordChatMessage, parse_reply

OnDiscordMessage = Callable[[DiscordChatMessage], Awaitable[None]]

RECONNECT_BASE_DELAY = 5.0
RECONNECT_MAX_DELAY = 60.0


def _channel_label(channel: discord.abc.Messageable) -> str:
    if isinstance(channel, discord.TextChannel):
        if channel.guild:
            return f"{channel.guild.name}/{channel.name}"
        return channel.name
    if isinstance(channel, discord.Thread):
        return channel.name
    return str(channel.id)


def parse_discord_message(message: discord.Message) -> DiscordChatMessage | None:
    if message.author.bot:
        return None

    content = message.content.strip()
    if not content and not message.attachments:
        return None

    if not content and message.attachments:
        content = " ".join(
            f"[attachment:{attachment.filename}]" for attachment in message.attachments
        )

    reply: dict[str, Any] | None = None
    if message.reference and message.reference.resolved:
        referenced = message.reference.resolved
        if isinstance(referenced, discord.Message):
            reply_author = referenced.author.display_name or referenced.author.name
            reply = {
                "message_id": str(referenced.id),
                "author_name": reply_author,
                "content": referenced.content[:200] if referenced.content else "",
            }

    raw: dict[str, Any] = {
        "source": "discord_gateway",
        "channel_id": str(message.channel.id),
        "message_type": str(message.type),
    }
    if message.guild:
        raw["guild_id"] = str(message.guild.id)
    if message.attachments:
        raw["attachments"] = [
            {"id": str(attachment.id), "filename": attachment.filename}
            for attachment in message.attachments
        ]

    author = message.author
    return DiscordChatMessage(
        message_id=str(message.id),
        author_id=str(author.id),
        author_name=author.display_name or author.name,
        login=author.name,
        content=content,
        timestamp=message.created_at.astimezone(UTC).isoformat(),
        channel=_channel_label(message.channel),
        channel_id=str(message.channel.id),
        guild_id=str(message.guild.id) if message.guild else None,
        reply=parse_reply(reply),
        raw=raw,
    )


def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    return intents


class DiscordIngressClient(discord.Client):
    def __init__(
        self,
        channel_id: int,
        on_message_cb: OnDiscordMessage,
        *,
        intents: discord.Intents | None = None,
    ) -> None:
        super().__init__(intents=intents or build_intents())
        self._channel_id = channel_id
        self._on_message_cb = on_message_cb

    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id != self._channel_id:
            return

        parsed = parse_discord_message(message)
        if parsed is None:
            return

        await self._on_message_cb(parsed)


async def listen_with_reconnect(
    token: str,
    channel_id: int,
    on_message: OnDiscordMessage,
    *,
    reconnect_base_delay: float = RECONNECT_BASE_DELAY,
    reconnect_max_delay: float = RECONNECT_MAX_DELAY,
) -> None:
    delay = reconnect_base_delay

    while True:
        client = DiscordIngressClient(channel_id, on_message)
        try:
            await client.start(token)
            delay = reconnect_base_delay
        except asyncio.CancelledError:
            if not client.is_closed():
                await client.close()
            raise
        except Exception as exc:
            print(f"Discord gateway error ({exc}), reconnecting in {delay}s...", flush=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, reconnect_max_delay)
        finally:
            if not client.is_closed():
                await client.close()
