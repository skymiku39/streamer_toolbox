from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import websockets

TWITCH_IRC_URL = "wss://irc-ws.chat.twitch.tv:443"
ANON_PASS = "SCHMOOPIIE"

PRIVMSG_RE = re.compile(r":([^!]+)![^ ]+ PRIVMSG #([^ ]+) :(.*)")

OnChatMessage = Callable[["IrcChatMessage"], Awaitable[None]]


@dataclass(frozen=True)
class IrcChatMessage:
    channel: str
    username: str
    login: str
    content: str
    message_id: str
    author_id: str | None


def _parse_tags(tag_string: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for part in tag_string.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            tags[key] = value
    return tags


def parse_privmsg(line: str) -> IrcChatMessage | None:
    if "PRIVMSG" not in line:
        return None

    tags: dict[str, str] = {}
    if line.startswith("@"):
        tag_string, line = line.split(" ", 1)
        tags = _parse_tags(tag_string[1:])

    match = PRIVMSG_RE.match(line)
    if not match:
        return None

    login = match.group(1)
    channel = match.group(2)
    content = match.group(3)
    username = tags.get("display-name") or login
    message_id = tags.get("id") or f"irc-{login}-{hash((channel, content, line)) & 0xFFFFFFFF:08x}"
    author_id = tags.get("user-id")

    return IrcChatMessage(
        channel=channel.lstrip("#"),
        username=username,
        login=login,
        content=content,
        message_id=message_id,
        author_id=author_id,
    )


async def listen_anonymous(channel: str, on_message: OnChatMessage) -> None:
    channel = channel.lstrip("#").lower()
    nick = f"justinfan{random.randint(10000, 99999)}"

    async with websockets.connect(TWITCH_IRC_URL) as ws:
        await ws.send(f"PASS {ANON_PASS}")
        await ws.send(f"NICK {nick}")
        await ws.send("CAP REQ :twitch.tv/tags twitch.tv/commands")
        await ws.send(f"JOIN #{channel}")

        async for raw in ws:
            for line in raw.split("\r\n"):
                if not line:
                    continue
                if line.startswith("PING"):
                    await ws.send(f"PONG {line.split()[1]}")
                    continue

                parsed = parse_privmsg(line)
                if parsed is None:
                    continue

                await on_message(parsed)


async def listen_anonymous_with_reconnect(
    channel: str,
    on_message: OnChatMessage,
    *,
    reconnect_delay: float = 5.0,
) -> None:
    while True:
        try:
            await listen_anonymous(channel, on_message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"IRC disconnected ({exc}), reconnecting in {reconnect_delay}s...", flush=True)
            await asyncio.sleep(reconnect_delay)
