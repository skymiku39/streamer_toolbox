from __future__ import annotations

import json

from ingress_twitch_stream.fetcher import TwitchStreamFetcher


def test_fetch_parses_live_gql_response(monkeypatch) -> None:
    payload = {
        "data": {
            "user": {
                "displayName": "Skymiku39",
                "stream": {
                    "title": "測試標題",
                    "type": "live",
                    "createdAt": "2026-06-13T08:00:00Z",
                    "viewersCount": 99,
                    "game": {"name": "Just Chatting"},
                },
            }
        }
    }

    class FakeResponse:
        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        "ingress_twitch_stream.fetcher.urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )

    snapshot = TwitchStreamFetcher().fetch("skymiku39")
    assert snapshot is not None
    assert snapshot.is_live is True
    assert snapshot.title == "測試標題"
    assert snapshot.game_name == "Just Chatting"
    assert snapshot.viewer_count == 99


def test_fetch_parses_offline_gql_response(monkeypatch) -> None:
    payload = {"data": {"user": {"displayName": "Skymiku39", "stream": None}}}

    class FakeResponse:
        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        "ingress_twitch_stream.fetcher.urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )

    snapshot = TwitchStreamFetcher().fetch("skymiku39")
    assert snapshot is not None
    assert snapshot.is_live is False
    assert snapshot.title == ""
