from __future__ import annotations

from pathlib import Path

from stream_store import (
    StreamTextStore,
    checkpoint_key_for_channel,
    resolve_session_for_channel,
    resolve_session_id,
    set_active_session_for_channel,
)


def test_checkpoint_key_per_channel() -> None:
    assert checkpoint_key_for_channel("Skymiku39") == "active_session_id:skymiku39"
    assert (
        checkpoint_key_for_channel("#test_channel_delta")
        == "active_session_id:test_channel_delta"
    )


def test_resolve_session_id_from_channel_and_day() -> None:
    session_id = resolve_session_id(
        channel="TestChannelGamma",
        day="20260612",
    )
    assert session_id == "testchannelgamma_20260612"


def test_resolve_session_id_ignores_mismatched_explicit() -> None:
    session_id = resolve_session_id(
        channel="skymiku39",
        explicit_session_id="skymiku39_20260613",
        day="20260612",
    )
    assert session_id == "skymiku39_20260613"

    session_id = resolve_session_id(
        channel="test_channel_beta",
        explicit_session_id="skymiku39_20260613",
        day="20260612",
    )
    assert session_id == "test_channel_beta_20260612"


def test_resolve_session_for_channel_uses_per_channel_checkpoint(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    set_active_session_for_channel(
        store,
        channel="room_a",
        session_id="room_a_20260612",
    )
    set_active_session_for_channel(
        store,
        channel="room_b",
        session_id="room_b_20260612",
    )
    assert resolve_session_for_channel(store, "room_a") == "room_a_20260612"
    assert resolve_session_for_channel(store, "room_b") == "room_b_20260612"
    store.close()


def test_legacy_global_checkpoint_only_when_prefix_matches(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    store.set_checkpoint("active_session_id", "room_a_20260612")
    assert resolve_session_for_channel(store, "room_a") == "room_a_20260612"
    assert resolve_session_for_channel(store, "room_b") is None or resolve_session_for_channel(
        store, "room_b"
    ) != "room_a_20260612"
    store.close()


def test_latest_session_id_for_channel(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    store.append_chat(
        session_id="alpha_20260612",
        channel="alpha",
        timestamp="2026-06-12T10:00:00+00:00",
        text="a",
        author="x",
        message_id="m1",
    )
    store.append_chat(
        session_id="beta_20260612",
        channel="beta",
        timestamp="2026-06-12T10:01:00+00:00",
        text="b",
        author="y",
        message_id="m2",
    )
    assert store.latest_session_id_for_channel("alpha") == "alpha_20260612"
    assert store.latest_session_id_for_channel("beta") == "beta_20260612"
    store.close()
