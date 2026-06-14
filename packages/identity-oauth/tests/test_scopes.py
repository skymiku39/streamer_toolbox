from __future__ import annotations

from identity_oauth.scopes import ALL_SCOPES, BOT_SCOPES, CHANNEL_SCOPES, scopes_for_role


def test_scopes_for_role_bot() -> None:
    scopes = scopes_for_role("bot", single_account=False)
    assert "user:write:chat" in scopes
    assert "channel:read:subscriptions" not in scopes


def test_scopes_for_role_channel() -> None:
    scopes = scopes_for_role("channel", single_account=False)
    assert "channel:read:subscriptions" in scopes
    assert "moderator:manage:chat_messages" not in scopes


def test_scopes_for_single_account_merges() -> None:
    scopes = scopes_for_role("bot", single_account=True)
    assert set(scopes) == set(ALL_SCOPES)
    assert len(scopes) == len(ALL_SCOPES)


def test_all_scopes_is_union_without_duplicates() -> None:
    assert len(ALL_SCOPES) == len(set([*BOT_SCOPES, *CHANNEL_SCOPES]))
