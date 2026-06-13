from __future__ import annotations

from datetime import UTC, datetime

from ingress_twitch_stream.fetcher import TwitchStreamSnapshot, elapsed_seconds
from ingress_twitch_stream.mapper import build_stream_metadata_event


def test_elapsed_seconds_from_started_at() -> None:
    started = "2026-06-13T08:00:00+00:00"
    now = datetime(2026, 6, 13, 10, 30, 0, tzinfo=UTC)
    assert elapsed_seconds(started, now=now) == 9000


def test_build_stream_metadata_event_live() -> None:
    snapshot = TwitchStreamSnapshot(
        channel="skymiku39",
        display_name="Skymiku39",
        is_live=True,
        title="Boss Rush",
        game_name="Dark Souls",
        started_at="2026-06-13T08:00:00+00:00",
        viewer_count=42,
        stream_url="https://www.twitch.tv/skymiku39",
        fetched_at=datetime(2026, 6, 13, 9, 0, 0, tzinfo=UTC),
    )
    event = build_stream_metadata_event(snapshot)
    assert event.topic == "stream.metadata"
    assert event.is_live is True
    assert event.game_name == "Dark Souls"
    assert event.duration_seconds == 3600
    assert event.viewer_count == 42
    assert event.snapshot_id


def test_build_stream_metadata_event_offline() -> None:
    snapshot = TwitchStreamSnapshot(
        channel="skymiku39",
        display_name="Skymiku39",
        is_live=False,
        title="",
        game_name="",
        started_at="",
        viewer_count=None,
        stream_url="https://www.twitch.tv/skymiku39",
        fetched_at=datetime(2026, 6, 13, 9, 0, 0, tzinfo=UTC),
    )
    event = build_stream_metadata_event(snapshot)
    assert event.is_live is False
    assert event.duration_seconds is None
