from __future__ import annotations

import pytest

from bus.config import rabbitmq_url, stream_exchange
from bus.topology import DEFAULT_EXCHANGE


def test_rabbitmq_url_default() -> None:
    assert rabbitmq_url() == "amqp://guest:guest@127.0.0.1:5672/"


def test_rabbitmq_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_URL", "amqp://user:pass@mq.example:5672/vhost")
    assert rabbitmq_url() == "amqp://user:pass@mq.example:5672/vhost"


def test_stream_exchange_default() -> None:
    assert stream_exchange() == DEFAULT_EXCHANGE


def test_stream_exchange_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAM_EXCHANGE", "custom_exchange")
    assert stream_exchange() == "custom_exchange"
