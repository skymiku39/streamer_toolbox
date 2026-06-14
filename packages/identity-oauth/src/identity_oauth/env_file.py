"""`.env` 檔案讀寫（bootstrap 寫入 refresh token 與 user id）。"""

from __future__ import annotations

from pathlib import Path

from identity_oauth.protocol import AccountRole
from identity_oauth.single_account import read_single_account_mode


def update_env_values(updates: dict[str, str], *, env_path: Path) -> None:
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    index_by_key: dict[str, int] = {}

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            index_by_key[key] = idx

    for key, value in updates.items():
        normalized = f"{key}={value}"
        if key in index_by_key:
            lines[index_by_key[key]] = normalized
        else:
            lines.append(normalized)

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def env_updates_for_authorization(
    role: AccountRole,
    *,
    refresh_token: str,
    user_id: str,
    single_account: bool,
) -> dict[str, str]:
    updates: dict[str, str] = {}
    if role == "channel":
        updates["TWITCH_CHANNEL_REFRESH_TOKEN"] = refresh_token
        updates["TWITCH_BROADCASTER_ID"] = user_id
        if single_account:
            updates["TWITCH_BOT_REFRESH_TOKEN"] = refresh_token
            updates["TWITCH_BOT_ID"] = user_id
    else:
        updates["TWITCH_BOT_REFRESH_TOKEN"] = refresh_token
        updates["TWITCH_BOT_ID"] = user_id
    return updates


def resolve_single_account_from_env(environ: dict[str, str]) -> bool:
    return read_single_account_mode(environ)
