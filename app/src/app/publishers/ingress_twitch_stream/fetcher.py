"""Twitch 直播 metadata 擷取（GQL，參考 hello_streamer）。"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
_GQL_URL = "https://gql.twitch.tv/gql"
_MAX_RETRIES = 2
_RETRY_DELAY = 3

_HEADERS = {
    "Client-ID": _CLIENT_ID,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "Origin": "https://www.twitch.tv",
    "Referer": "https://www.twitch.tv/",
}

_GQL_QUERY = """
query StreamStatus($login: String!) {
  user(login: $login) {
    displayName
    stream {
      title
      type
      createdAt
      viewersCount
      game {
        name
      }
    }
  }
}
"""


@dataclass(frozen=True)
class TwitchStreamSnapshot:
    channel: str
    display_name: str
    is_live: bool
    title: str
    game_name: str
    started_at: str
    viewer_count: int | None
    stream_url: str
    fetched_at: datetime


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def elapsed_seconds(started_at: str, *, now: datetime | None = None) -> int | None:
    start = _parse_iso_datetime(started_at)
    if start is None:
        return None
    reference = now or datetime.now(UTC)
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    delta = reference - start.astimezone(UTC)
    if delta < timedelta(0):
        return 0
    return int(delta.total_seconds())


class TwitchStreamFetcher:
    """透過 Twitch 網頁 GQL 查詢直播標題、分類、開播時間與觀眾數。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def fetch(self, channel: str) -> TwitchStreamSnapshot | None:
        login = channel.lstrip("#").lower()
        data = self._gql(_GQL_QUERY, {"login": login})
        if data is None:
            return None
        try:
            user = data["data"]["user"]
            if user is None:
                return None
            stream = user.get("stream")
            is_live = stream is not None and stream.get("type") == "live"
            title = ""
            game_name = ""
            started_at = ""
            viewer_count: int | None = None
            if stream:
                title = str(stream.get("title", "") or "")
                started_at = str(stream.get("createdAt", "") or "")
                game = stream.get("game") or {}
                game_name = str(game.get("name", "") or "")
                raw_viewers = stream.get("viewersCount")
                if raw_viewers is not None:
                    viewer_count = int(raw_viewers)
            return TwitchStreamSnapshot(
                channel=login,
                display_name=str(user.get("displayName", "") or login),
                is_live=is_live,
                title=title,
                game_name=game_name,
                started_at=started_at,
                viewer_count=viewer_count,
                stream_url=f"https://www.twitch.tv/{login}",
                fetched_at=datetime.now(UTC),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse Twitch GQL for %s: %s", login, exc)
            return None

    def _gql(self, query: str, variables: dict[str, str]) -> dict | None:
        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        channel_name = variables.get("login", "")
        for attempt in range(_MAX_RETRIES + 1):
            try:
                request = urllib.request.Request(
                    _GQL_URL,
                    data=payload,
                    headers=_HEADERS,
                    method="POST",
                )
                with self._lock:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        raw = response.read().decode("utf-8")
                data = json.loads(raw)
                if "errors" in data:
                    logger.warning("Twitch GQL errors for %s: %s", channel_name, data["errors"])
                return data
            except urllib.error.HTTPError as exc:
                logger.warning(
                    "Twitch HTTP %s for %s (attempt %d/%d)",
                    exc.code,
                    channel_name,
                    attempt + 1,
                    _MAX_RETRIES + 1,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue
                return None
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                logger.warning(
                    "Twitch request failed for %s: %s (attempt %d/%d)",
                    channel_name,
                    exc,
                    attempt + 1,
                    _MAX_RETRIES + 1,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue
                return None
        return None
