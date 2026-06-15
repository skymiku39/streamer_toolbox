from __future__ import annotations

from typing import Any

import httpx


async def fetch_json(
    url: str,
    *,
    timeout: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> tuple[int, Any]:
    if client is None:
        async with httpx.AsyncClient(timeout=timeout) as session:
            response = await session.get(url)
            return response.status_code, response.json()
    response = await client.get(url, timeout=timeout)
    return response.status_code, response.json()
