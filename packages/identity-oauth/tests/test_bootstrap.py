from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from identity_oauth.bootstrap import (
    build_authorization_url,
    exchange_code_for_token,
    fetch_token_info,
)


def test_build_authorization_url_contains_required_params() -> None:
    url = build_authorization_url(
        client_id="client",
        redirect_uri="http://localhost:17563",
        scopes=["chat:read", "chat:edit"],
        force_verify=True,
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.path == "/oauth2/authorize"
    assert query["client_id"] == ["client"]
    assert query["redirect_uri"] == ["http://localhost:17563"]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["chat:read chat:edit"]
    assert query["force_verify"] == ["true"]


def test_exchange_code_for_token_parses_response() -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(
        return_value={
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "expires_in": 3600,
            "token_type": "bearer",
        }
    )
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("identity_oauth.bootstrap.httpx.AsyncClient", return_value=client):
        payload = asyncio.run(
            exchange_code_for_token(
                client_id="client",
                client_secret="secret",
                redirect_uri="http://localhost:17563",
                code="auth-code",
            )
        )

    assert payload["access_token"] == "access-1"
    assert payload["refresh_token"] == "refresh-1"


def test_fetch_token_info_returns_user_id() -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(
        return_value={
            "client_id": "client",
            "login": "bot_user",
            "user_id": "42",
            "scopes": ["chat:edit"],
        }
    )
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("identity_oauth.bootstrap.httpx.AsyncClient", return_value=client):
        info = asyncio.run(fetch_token_info("access-1"))

    assert info["user_id"] == "42"
    assert info["login"] == "bot_user"
