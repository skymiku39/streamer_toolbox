from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FirstChatSession:
    stream_id: str = ""
    started_at: str = ""
    claimed: bool = False


@dataclass
class FirstChatTracker:
    excluded_identities: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "streamlabs",
                "nightbot",
                "streamelements",
            }
        )
    )
    _sessions: dict[str, FirstChatSession] = field(default_factory=dict)

    @staticmethod
    def _channel_key(channel_name: str) -> str:
        return str(channel_name or "").strip().lstrip("#").lower()

    @staticmethod
    def _identity_key(value: str) -> str:
        return str(value or "").strip().lstrip("@").lower()

    def arm_session(
        self,
        *,
        channel_name: str,
        stream_id: str = "",
        started_at: str = "",
    ) -> FirstChatSession | None:
        key = self._channel_key(channel_name)
        if not key:
            return None
        session = FirstChatSession(
            stream_id=str(stream_id or ""),
            started_at=str(started_at or ""),
            claimed=False,
        )
        self._sessions[key] = session
        return session

    def clear_session(self, channel_name: str) -> bool:
        key = self._channel_key(channel_name)
        if not key:
            return False
        return self._sessions.pop(key, None) is not None

    def is_excluded(self, *, login: str, display_name: str) -> bool:
        identities = {
            self._identity_key(login),
            self._identity_key(display_name),
        }
        identities.discard("")
        return bool(identities & self.excluded_identities)

    def try_claim(
        self,
        *,
        channel_name: str,
        login: str,
        display_name: str,
        broadcaster_id: str,
        is_broadcaster: bool,
        is_shared_chat: bool,
    ) -> dict[str, Any] | None:
        if is_shared_chat or is_broadcaster:
            return None
        if self.is_excluded(login=login, display_name=display_name):
            return None

        key = self._channel_key(channel_name)
        session = self._sessions.get(key)
        if session is None or session.claimed:
            return None

        session.claimed = True
        return {
            "channel": key,
            "stream_id": session.stream_id,
            "started_at": session.started_at,
            "broadcaster_id": broadcaster_id,
        }
