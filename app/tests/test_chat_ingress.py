from __future__ import annotations

from app.processes.chat_ingress import (
    CHAT_INGRESS_EVENTSUB,
    CHAT_INGRESS_IRC_FALLBACK,
    EVENTSUB_PROCESS,
    IRC_FALLBACK_PROCESS,
    parse_chat_ingress_status,
)
from app.processes.registry import registry
from app.processes.runner import _split_chat_ingress_specs


def test_parse_chat_ingress_status_from_plain_line() -> None:
    assert parse_chat_ingress_status("CHAT_INGRESS_STATUS=eventsub\n") == CHAT_INGRESS_EVENTSUB


def test_parse_chat_ingress_status_from_prefixed_runner_line() -> None:
    line = "[ingress-twitch-eventsub] CHAT_INGRESS_STATUS=irc_fallback\n"
    assert parse_chat_ingress_status(line) == CHAT_INGRESS_IRC_FALLBACK


def test_split_chat_ingress_specs_extracts_eventsub_and_fallback() -> None:
    eventsub = registry.get(EVENTSUB_PROCESS)
    irc = registry.get(IRC_FALLBACK_PROCESS)
    bot = registry.get("sub-bot-logic")

    remaining, supervised, fallback = _split_chat_ingress_specs(
        [eventsub, irc, bot],
        chat_fallback=True,
    )
    assert supervised is eventsub
    assert fallback is irc
    assert [spec.name for spec in remaining] == ["sub-bot-logic"]


def test_split_chat_ingress_specs_disabled_keeps_original_list() -> None:
    eventsub = registry.get(EVENTSUB_PROCESS)
    irc = registry.get(IRC_FALLBACK_PROCESS)
    specs = [eventsub, irc]

    remaining, supervised, fallback = _split_chat_ingress_specs(specs, chat_fallback=False)
    assert remaining == specs
    assert supervised is None
    assert fallback is None
