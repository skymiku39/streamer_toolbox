from __future__ import annotations

from typing import Any

import httpx

HELIX_BASE = "https://api.twitch.tv/helix"
OAUTH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"


async def fetch_app_access_token(
    client_id: str,
    client_secret: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }
    if client is None:
        async with httpx.AsyncClient(timeout=15.0) as session:
            response = await session.post(OAUTH_TOKEN_URL, data=payload)
            response.raise_for_status()
            data = response.json()
    else:
        response = await client.post(OAUTH_TOKEN_URL, data=payload, timeout=15.0)
        response.raise_for_status()
        data = response.json()
    token = str(data.get("access_token", "")).strip()
    if not token:
        raise RuntimeError("Helix app access token missing in response")
    return token


async def resolve_user_login_to_id(
    login: str,
    *,
    client_id: str,
    access_token: str,
    client: httpx.AsyncClient,
) -> str:
    normalized = login.lstrip("#").strip().lower()
    if not normalized:
        return ""
    response = await client.get(
        f"{HELIX_BASE}/users",
        params={"login": normalized},
        headers={
            "Client-Id": client_id,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=15.0,
    )
    response.raise_for_status()
    data = response.json()
    users = data.get("data", [])
    if not users:
        return ""
    return str(users[0].get("id", "")).strip()


async def helix_get(
    path: str,
    *,
    client_id: str,
    access_token: str,
    client: httpx.AsyncClient,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    response = await client.get(
        f"{HELIX_BASE}/{path.lstrip('/')}",
        params=params or {},
        headers={
            "Client-Id": client_id,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=15.0,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}
