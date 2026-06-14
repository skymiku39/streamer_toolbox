from __future__ import annotations

from pathlib import Path

from identity_oauth.env_file import env_updates_for_authorization, update_env_values


def test_env_updates_for_channel_dual_account() -> None:
    updates = env_updates_for_authorization(
        "channel",
        refresh_token="chan-refresh",
        user_id="123",
        single_account=False,
    )
    assert updates == {
        "TWITCH_CHANNEL_REFRESH_TOKEN": "chan-refresh",
        "TWITCH_BROADCASTER_ID": "123",
    }


def test_env_updates_for_bot_dual_account() -> None:
    updates = env_updates_for_authorization(
        "bot",
        refresh_token="bot-refresh",
        user_id="456",
        single_account=False,
    )
    assert updates == {
        "TWITCH_BOT_REFRESH_TOKEN": "bot-refresh",
        "TWITCH_BOT_ID": "456",
    }


def test_env_updates_for_single_account_mirrors_bot() -> None:
    updates = env_updates_for_authorization(
        "channel",
        refresh_token="shared",
        user_id="999",
        single_account=True,
    )
    assert updates["TWITCH_BOT_REFRESH_TOKEN"] == "shared"
    assert updates["TWITCH_BOT_ID"] == "999"


def test_update_env_values_preserves_comments_and_updates_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# header\nTWITCH_CLIENT_ID=old\nTWITCH_CHANNEL=foo\n",
        encoding="utf-8",
    )
    update_env_values(
        {
            "TWITCH_CLIENT_ID": "new-id",
            "TWITCH_BOT_ID": "bot-1",
        },
        env_path=env,
    )
    text = env.read_text(encoding="utf-8")
    assert "# header" in text
    assert "TWITCH_CLIENT_ID=new-id" in text
    assert "TWITCH_CHANNEL=foo" in text
    assert "TWITCH_BOT_ID=bot-1" in text
    assert "TWITCH_CLIENT_ID=old" not in text
