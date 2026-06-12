from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pkg_events import (
    SOURCE_CHARACTER_BRAIN,
    TOPIC_CHARACTER_TURN,
    TOPIC_CHAT_REPLY,
    CharacterTurnEvent,
    ChatMessageEvent,
    ChatReplyEvent,
)
from pkg_safety import SafetyFilter

from sub_character_brain.config import CharacterConfig
from sub_character_brain.llm import CharacterLlm, MemoryTurn

class CharacterBrain:
    def __init__(
        self,
        config: CharacterConfig,
        llm: CharacterLlm,
        safety: SafetyFilter,
        publish: Callable[[str, dict[str, Any]], None],
    ) -> None:
        self._config = config
        self._llm = llm
        self._safety = safety
        self._publish = publish
        self._memory: list[MemoryTurn] = []

    def handle(self, payload: dict[str, Any]) -> None:
        event = ChatMessageEvent.from_dict(payload)
        if not self._should_respond(event):
            return

        user_text = self._extract_user_text(event.content)
        filtered_input = self._safety.filter_input(user_text)
        if filtered_input is None:
            return

        response = self._llm.generate(
            config=self._config,
            author_name=event.author_name,
            user_text=filtered_input,
            memory=list(self._memory),
        )
        filtered_output = self._safety.filter_output(response.text)
        if filtered_output is None:
            return

        turn_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

        turn = CharacterTurnEvent(
            schema_version=1,
            topic=TOPIC_CHARACTER_TURN,
            turn_id=turn_id,
            correlation_id=event.message_id,
            text=filtered_output,
            emotion=response.emotion,
            emotion_intensity=response.emotion_intensity,
            language=self._config.language,
            timestamp=timestamp,
        )
        self._publish(TOPIC_CHARACTER_TURN, turn.to_dict())
        self._append_memory(event.author_name, filtered_input, filtered_output)

        if self._config.publish_chat_reply:
            reply_content = filtered_output[: self._config.chat_reply_max_length]
            reply = ChatReplyEvent(
                schema_version=1,
                topic=TOPIC_CHAT_REPLY,
                platform=event.platform,
                channel=event.channel or "",
                content=reply_content,
                source=SOURCE_CHARACTER_BRAIN,
                sender="bot",
                reply_to_message_id=event.message_id,
                correlation_id=event.message_id,
            )
            self._publish(TOPIC_CHAT_REPLY, reply.to_dict())

    def _should_respond(self, event: ChatMessageEvent) -> bool:
        if self._config.respond_to_all:
            return True
        prefix = self._config.trigger_prefix
        if not prefix:
            return True
        return event.content.strip().startswith(prefix)

    def _extract_user_text(self, content: str) -> str:
        stripped = content.strip()
        prefix = self._config.trigger_prefix
        if prefix and stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
        return stripped

    def _append_memory(self, author_name: str, user_text: str, character_text: str) -> None:
        self._memory.append(
            MemoryTurn(
                author_name=author_name,
                user_text=user_text,
                character_text=character_text,
            )
        )
        overflow = len(self._memory) - self._config.memory_max_turns
        if overflow > 0:
            del self._memory[:overflow]
