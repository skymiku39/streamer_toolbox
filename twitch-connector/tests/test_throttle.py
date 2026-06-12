import time

from twitch_connector.throttle import MessageThrottle


def test_per_channel_interval_blocks_rapid_sends() -> None:
    throttle = MessageThrottle(
        window_limit=100,
        window_seconds=30.0,
        per_channel_interval_seconds=0.2,
    )
    throttle.wait("TestChannel")
    start = time.monotonic()
    throttle.wait("TestChannel")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.15


def test_global_window_limit() -> None:
    throttle = MessageThrottle(
        window_limit=2,
        window_seconds=1.0,
        per_channel_interval_seconds=0.0,
    )
    throttle.wait("a")
    throttle.wait("b")
    start = time.monotonic()
    throttle.wait("c")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.05
