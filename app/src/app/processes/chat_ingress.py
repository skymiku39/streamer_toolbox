from __future__ import annotations

CHAT_INGRESS_STATUS_PREFIX = "CHAT_INGRESS_STATUS="
CHAT_INGRESS_EVENTSUB = "eventsub"
CHAT_INGRESS_IRC_FALLBACK = "irc_fallback"
CHAT_FALLBACK_EXIT_CODE = 2
EVENTSUB_PROCESS = "ingress-twitch-eventsub"
IRC_FALLBACK_PROCESS = "ingress-ttv-read"
CHAT_INGRESS_STARTUP_TIMEOUT_SECONDS = 90


def parse_chat_ingress_status(line: str) -> str | None:
    for part in line.split():
        if part.startswith(CHAT_INGRESS_STATUS_PREFIX):
            return part.removeprefix(CHAT_INGRESS_STATUS_PREFIX).strip()
    if CHAT_INGRESS_STATUS_PREFIX in line:
        return line.split(CHAT_INGRESS_STATUS_PREFIX, 1)[1].strip()
    return None
