from __future__ import annotations

from typing import Any


def parse_badge_response(response: dict[str, Any]) -> dict[str, str]:
    """Convert Helix chat/badges response to ``set_id/version`` -> image URL map."""
    result: dict[str, str] = {}
    for badge_set in response.get("data", []):
        if not isinstance(badge_set, dict):
            continue
        set_id = str(badge_set.get("set_id", "")).strip()
        if not set_id:
            continue
        versions = badge_set.get("versions", [])
        if not isinstance(versions, list):
            continue
        for version in versions:
            if not isinstance(version, dict):
                continue
            vid = str(version.get("id", "")).strip()
            if not vid:
                continue
            for key in ("image_url_2x", "image_url_4x", "image_url_1x"):
                url = version.get(key)
                if isinstance(url, str) and url.strip():
                    result[f"{set_id}/{vid}"] = url.strip()
                    break
    return result


def badge_key(set_id: str, version: str) -> str:
    return f"{set_id}/{version}"
