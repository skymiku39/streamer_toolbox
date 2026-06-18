"""Twitch Helix chat/messages 發送（對照 twitch_api api/chat.py）。"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from twitch_connector.throttle import MessageThrottle
from twitch_connector.token_provider import ConnectorTokenProvider

HELIX_BASE = "https://api.twitch.tv/helix"


class TwitchSendError(RuntimeError):
    pass


class TwitchChatSender:
    def __init__(
        self,
        token_provider: ConnectorTokenProvider,
        throttle: MessageThrottle | None = None,
    ) -> None:
        self._token_provider = token_provider
        self._throttle = throttle or MessageThrottle()
        self._broadcaster_cache: dict[str, str] = {}

    def send(
        self,
        channel: str,
        content: str,
        *,
        reply_to_message_id: str | None = None,
    ) -> None:
        normalized_channel = channel.lstrip("#").lower()
        broadcaster_id = self._resolve_broadcaster_id(normalized_channel)
        self._throttle.wait(normalized_channel)
        body: dict[str, Any] = {
            "broadcaster_id": broadcaster_id,
            "sender_id": self._token_provider.sender_id(),
            "message": content,
        }
        if reply_to_message_id:
            body["reply_parent_message_id"] = reply_to_message_id
        self._request("POST", "chat/messages", data=body)

    def _resolve_broadcaster_id(self, channel: str) -> str:
        cached = self._broadcaster_cache.get(channel)
        if cached:
            return cached
        response = self._request("GET", "users", params={"login": channel})
        users = response.get("data", [])
        if not users:
            raise TwitchSendError(f"broadcaster not found: {channel}")
        broadcaster_id = str(users[0].get("id", "")).strip()
        if not broadcaster_id:
            raise TwitchSendError(f"invalid broadcaster id for channel: {channel}")
        self._broadcaster_cache[channel] = broadcaster_id
        return broadcaster_id

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{HELIX_BASE}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        headers = {
            "Client-Id": self._token_provider.client_id(),
            "Authorization": f"Bearer {self._token_provider.access_token()}",
            "Content-Type": "application/json",
        }
        body_bytes = json.dumps(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TwitchSendError(f"Helix {method} {path} failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise TwitchSendError(f"Helix {method} {path} network error: {exc}") from exc
