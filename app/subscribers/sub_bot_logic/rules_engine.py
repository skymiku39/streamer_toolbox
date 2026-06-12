"""規則 BOT 核心：chat.message / eventsub.* → chat.reply。"""

from __future__ import annotations

import time
from typing import Any

from pkg_events import (
    SOURCE_LOGIC_COMMANDS,
    SOURCE_LOGIC_EVENTS,
    SOURCE_LOGIC_KEYWORDS,
    TOPIC_CHAT_MESSAGE,
    TOPIC_EVENTSUB_PREFIX,
    ChatMessageEvent,
    ChatReplyEvent,
    EventSubEvent,
)

from sub_bot_logic.eventsub_mapper import template_category, template_key, template_kwargs
from sub_bot_logic.irc_events import irc_event_key, irc_template_kwargs
from sub_bot_logic.redemption_map import RedemptionResponseMap
from sub_bot_logic.response_map import BotResponseMap, _normalize_command_key
from sub_bot_logic.role import resolve_role

_BUILTIN_COMMANDS: dict[str, str] = {
    "ping": "測試 Bot 是否在線",
    "hello": "打招呼",
    "info": "顯示 Bot 資訊",
    "commands": "顯示可用指令",
    "echo": "重複訊息",
    "uptime": "顯示 Bot 運作狀態",
    "announce": "發送公告",
}


class BotRulesEngine:
    def __init__(
        self,
        response_map: BotResponseMap,
        redemption_map: RedemptionResponseMap,
        *,
        command_prefix: str = "!",
        bot_identity: str = "Streamer Toolbox Bot",
    ) -> None:
        self._response_map = response_map
        self._redemption_map = redemption_map
        self._command_prefix = command_prefix
        self._bot_identity = bot_identity
        self._keyword_cooldowns: dict[str, float] = {}

    def reload(self) -> None:
        self._response_map.reload()
        self._redemption_map.reload()

    def process_payload(self, payload: dict[str, Any]) -> ChatReplyEvent | None:
        topic = str(payload.get("topic", ""))
        if topic == TOPIC_CHAT_MESSAGE:
            return self.process_chat_message(ChatMessageEvent.from_dict(payload))
        if topic.startswith(TOPIC_EVENTSUB_PREFIX):
            return self.process_eventsub(EventSubEvent.from_dict(payload))
        return None

    def process_chat_message(self, message: ChatMessageEvent) -> ChatReplyEvent | None:
        irc_key = irc_event_key(message)
        if irc_key and str(message.raw.get("message_type", "textMessage")) != "textMessage":
            return self._reply_from_template(
                message=message,
                category="event",
                template_key=irc_key,
                kwargs=irc_template_kwargs(message, irc_key),
                source=SOURCE_LOGIC_EVENTS,
            )

        content = message.content.strip()
        if not content:
            return None

        prefix = self._command_prefix
        if prefix and content.startswith(prefix):
            return self._process_command(message, content)

        return self._process_keyword(message, content)

    def process_eventsub(self, event: EventSubEvent) -> ChatReplyEvent | None:
        if event.event_type == "redemption":
            return self._process_redemption(event)
        if event.event_type in {"stream_online", "stream_offline"}:
            return None

        category = template_category(event.event_type)
        if category is None:
            return None

        key = template_key(event.event_type)
        kwargs = template_kwargs(event)
        channel = (
            event.channel
            or str(event.payload.get("channel") or event.payload.get("broadcaster_name") or "")
        ).lstrip("#")
        if not channel:
            return None

        content = self._response_map.format(category, key, **kwargs)
        if not content:
            return None

        return ChatReplyEvent(
            schema_version=1,
            topic="chat.reply",
            platform=event.platform,
            channel=channel.lstrip("#"),
            content=content,
            source=SOURCE_LOGIC_EVENTS,
            correlation_id=event.broadcaster_id,
        )

    def _process_redemption(self, event: EventSubEvent) -> ChatReplyEvent | None:
        kwargs = template_kwargs(event)
        user = str(kwargs.get("user") or event.user_name or "")
        title = str(kwargs.get("title") or "")
        cost = int(kwargs.get("cost") or 0)
        user_input = str(kwargs.get("user_input") or "")
        content = self._redemption_map.get_response(title, user, cost, user_input)
        channel = (event.channel or "").lstrip("#")
        if not channel or not content:
            return None
        return ChatReplyEvent(
            schema_version=1,
            topic="chat.reply",
            platform=event.platform,
            channel=channel,
            content=content,
            source=SOURCE_LOGIC_EVENTS,
            correlation_id=event.broadcaster_id,
        )

    def _process_command(self, message: ChatMessageEvent, content: str) -> ChatReplyEvent | None:
        parts = content.split(maxsplit=1)
        invoked = _normalize_command_key(parts[0])
        tail = parts[1].strip() if len(parts) > 1 else ""
        role = resolve_role(message.badges)
        channel = (message.channel or "").lstrip("#")
        author = message.author_name

        if not self._response_map.can_use_command(invoked, role):
            permission = self._response_map.get_command_permission(invoked)
            if not permission["enabled"]:
                denied = f"❌ !{invoked} 目前已停用。"
            else:
                denied = (
                    f"❌ {author}，你沒有使用 !{invoked} 的權限"
                    f"（最低需要：{permission['min_role']}）。"
                )
            return self._make_reply(
                message,
                denied,
                source=SOURCE_LOGIC_COMMANDS,
            )

        if invoked == "commands":
            visible = self._visible_commands(role)
            if not visible:
                return self._make_reply(message, "📋 目前沒有你可使用的指令。", SOURCE_LOGIC_COMMANDS)
            preview = " | ".join(visible[:25])
            suffix = " | …" if len(visible) > 25 else ""
            return self._make_reply(
                message,
                f"📋 可用指令: {preview}{suffix}",
                SOURCE_LOGIC_COMMANDS,
            )

        kwargs = {
            "author": author,
            "channel": channel,
            "identity": self._bot_identity,
            "message": tail,
        }
        rendered = self._response_map.format("command", invoked, **kwargs)
        if not rendered:
            return None
        return self._make_reply(message, rendered, SOURCE_LOGIC_COMMANDS)

    def _process_keyword(self, message: ChatMessageEvent, content: str) -> ChatReplyEvent | None:
        rules = self._response_map.get_keyword_rules(enabled_only=True)
        if not rules:
            return None

        now = time.monotonic()
        for rule in rules:
            trigger = str(rule.get("trigger", "")).strip()
            if not trigger:
                continue
            case_sensitive = bool(rule.get("case_sensitive", False))
            source_text = content if case_sensitive else content.lower()
            source_trigger = trigger if case_sensitive else trigger.lower()
            mode = str(rule.get("match_mode", "contains")).strip().lower()
            matched = (
                source_text == source_trigger if mode == "exact" else source_trigger in source_text
            )
            if not matched:
                continue

            rule_id = str(rule.get("id", trigger)).strip() or trigger
            cooldown = int(rule.get("cooldown_sec", 0) or 0)
            last_at = self._keyword_cooldowns.get(rule_id, 0.0)
            if cooldown > 0 and (now - last_at) < cooldown:
                continue

            response = self._response_map.format_keyword_response(
                rule,
                author=message.author_name,
                login=message.login or message.author_name,
                channel=(message.channel or "").lstrip("#"),
                message=content,
            )
            if not response:
                continue

            self._keyword_cooldowns[rule_id] = now
            return self._make_reply(message, response, SOURCE_LOGIC_KEYWORDS)

        return None

    def _visible_commands(self, role: str) -> list[str]:
        visible: list[str] = []
        templates = self._response_map.get_category("command")
        for key in sorted(set(templates.keys()) | set(_BUILTIN_COMMANDS.keys())):
            if not self._response_map.can_use_command(key, role):
                continue
            desc = _BUILTIN_COMMANDS.get(key, "自訂指令")
            visible.append(f"!{key} - {desc}")
        return visible

    def _reply_from_template(
        self,
        *,
        message: ChatMessageEvent,
        category: str,
        template_key: str,
        kwargs: dict[str, Any],
        source: str,
    ) -> ChatReplyEvent | None:
        content = self._response_map.format(category, template_key, **kwargs)
        if not content:
            return None
        return self._make_reply(message, content, source)

    def _make_reply(
        self,
        message: ChatMessageEvent,
        content: str,
        source: str,
    ) -> ChatReplyEvent:
        return ChatReplyEvent(
            schema_version=1,
            topic="chat.reply",
            platform=message.platform,
            channel=(message.channel or "").lstrip("#"),
            content=content,
            source=source,
            correlation_id=message.message_id,
        )
