"""首次 Twitch OAuth 授權（本 repo 內建，不需 twitch_api）。"""

from __future__ import annotations

from identity_oauth.bootstrap import run_authorize_cli

if __name__ == "__main__":
    raise SystemExit(run_authorize_cli())
