from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from game_info.models import GameReviewInfo

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
_IGDB_URL = "https://api.igdb.com/v4/games"
_DEFAULT_TIMEOUT = 10.0
_DEFAULT_CACHE_TTL = 3600


class IgdbGameInfoProvider:
    """透過 IGDB（Twitch 遊戲資料庫）查詢評分與簡介。"""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        cache_ttl_seconds: int = _DEFAULT_CACHE_TTL,
        timeout_sec: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._cache_ttl_seconds = max(60, cache_ttl_seconds)
        self._timeout_sec = timeout_sec
        self._lock = threading.Lock()
        self._token: str = ""
        self._token_expires_at: float = 0.0
        self._cache: dict[str, tuple[float, GameReviewInfo | None]] = {}

    def lookup(self, game_name: str) -> GameReviewInfo | None:
        query = game_name.strip()
        if not query or not self._client_id or not self._client_secret:
            return None
        cache_key = query.lower()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None and cached[0] > time.monotonic():
                return cached[1]
        result = self._fetch_game(query)
        with self._lock:
            self._cache[cache_key] = (
                time.monotonic() + self._cache_ttl_seconds,
                result,
            )
        return result

    def _fetch_game(self, game_name: str) -> GameReviewInfo | None:
        token = self._ensure_token()
        if not token:
            return None
        escaped = game_name.replace('"', '\\"')
        body = (
            f'search "{escaped}"; '
            "fields name,summary,aggregated_rating,total_rating,"
            "first_release_date,genres.name,platforms.name; "
            "limit 1;"
        )
        rows = self._post_igdb(body, token)
        if not rows:
            return None
        return _parse_game_row(rows[0])

    def _ensure_token(self) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._token_expires_at - 60:
                return self._token
        token, expires_in = _fetch_app_access_token(
            self._client_id,
            self._client_secret,
            timeout_sec=self._timeout_sec,
        )
        if not token:
            return ""
        with self._lock:
            self._token = token
            self._token_expires_at = time.monotonic() + max(60, expires_in)
            return self._token

    def _post_igdb(self, body: str, token: str) -> list[dict[str, Any]]:
        request = urllib.request.Request(
            _IGDB_URL,
            data=body.encode("utf-8"),
            headers={
                "Client-ID": self._client_id,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else []
                return data if isinstance(data, list) else []
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError) as exc:
            logger.warning("IGDB lookup failed for body=%r: %s", body[:80], exc)
            return []


def _fetch_app_access_token(
    client_id: str,
    client_secret: str,
    *,
    timeout_sec: float,
) -> tuple[str, int]:
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
    )
    request = urllib.request.Request(
        f"{_TOKEN_URL}?{query}",
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
            token = str(payload.get("access_token", "") or "")
            expires_in = int(payload.get("expires_in", 0) or 0)
            return token, expires_in
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError) as exc:
        logger.warning("IGDB token fetch failed: %s", exc)
        return "", 0


def _parse_game_row(row: dict[str, Any]) -> GameReviewInfo | None:
    name = str(row.get("name", "") or "").strip()
    if not name:
        return None
    summary = str(row.get("summary", "") or "").strip()
    critic = row.get("aggregated_rating")
    user = row.get("total_rating")
    critic_score = float(critic) if critic is not None else None
    user_score = float(user) if user is not None else None
    genres = tuple(
        str(item.get("name", "") or "").strip()
        for item in (row.get("genres") or [])
        if str(item.get("name", "") or "").strip()
    )
    platforms = tuple(
        str(item.get("name", "") or "").strip()
        for item in (row.get("platforms") or [])
        if str(item.get("name", "") or "").strip()
    )
    release_year = _release_year(row.get("first_release_date"))
    return GameReviewInfo(
        name=name,
        summary=summary,
        critic_score=critic_score,
        user_score=user_score,
        genres=genres,
        platforms=platforms,
        release_year=release_year,
        source="igdb",
    )


def _release_year(timestamp: Any) -> int | None:
    if timestamp is None:
        return None
    try:
        value = int(timestamp)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(value, tz=UTC).year
