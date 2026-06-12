from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

from identity_oauth.env_provider import EnvTokenProvider


async def _show_status() -> int:
    provider = EnvTokenProvider()
    missing = [
        name
        for name, value in {
            "TWITCH_CLIENT_ID": provider.client_id,
            "TWITCH_CLIENT_SECRET": provider.client_secret,
            "TWITCH_BOT_ID": provider.bot_id,
            "TWITCH_BROADCASTER_ID": provider.broadcaster_id,
            "TWITCH_REFRESH_TOKEN": (os.environ.get("TWITCH_REFRESH_TOKEN") or "").strip(),
        }.items()
        if not value
    ]
    if missing:
        print("Missing env:", ", ".join(missing), file=sys.stderr)
        return 1

    creds = await provider.get_credentials()
    print(f"bot_id={creds.bot_id}")
    print(f"broadcaster_id={creds.broadcaster_id}")
    print(f"access_token_prefix={creds.access_token[:8]}...")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Twitch OAuth token provider status")
    parser.parse_args(argv)
    return asyncio.run(_show_status())


if __name__ == "__main__":
    raise SystemExit(main())
