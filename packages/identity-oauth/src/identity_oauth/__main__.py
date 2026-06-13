from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

from identity_oauth.multi_account_provider import MultiAccountTokenProvider
from identity_oauth.protocol import AccountRole


async def _show_status(role: AccountRole) -> int:
    provider = MultiAccountTokenProvider()
    missing = [
        name
        for name, value in {
            "TWITCH_CLIENT_ID": provider.client_id,
            "TWITCH_CLIENT_SECRET": provider.client_secret,
            "TWITCH_BOT_ID": provider.bot_id,
            "TWITCH_BROADCASTER_ID": provider.broadcaster_id,
        }.items()
        if not value
    ]
    refresh_key = (
        "TWITCH_CHANNEL_REFRESH_TOKEN"
        if role == "channel"
        else "TWITCH_BOT_REFRESH_TOKEN"
    )
    if not (os.environ.get(refresh_key) or os.environ.get("TWITCH_REFRESH_TOKEN") or "").strip():
        missing.append(f"{refresh_key} (or TWITCH_REFRESH_TOKEN)")
    if missing:
        print("Missing env:", ", ".join(missing), file=sys.stderr)
        return 1

    creds = await provider.get_credentials(role)
    print(f"role={role}")
    print(f"single_account={provider.single_account}")
    print(f"bot_id={creds.bot_id}")
    print(f"broadcaster_id={creds.broadcaster_id}")
    print(f"access_token_prefix={creds.access_token[:8]}...")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Twitch OAuth token provider status")
    parser.add_argument(
        "--role",
        choices=["channel", "bot"],
        default="bot",
        help="Account role to validate (default: bot)",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_show_status(args.role))


if __name__ == "__main__":
    raise SystemExit(main())
