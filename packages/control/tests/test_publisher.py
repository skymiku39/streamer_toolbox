from __future__ import annotations

from unittest.mock import MagicMock, patch

from control.publisher import publish_config_changed_blocking, try_publish_config_changed
from events import TOPIC_CONFIG_CHANGED


def test_publish_config_changed_blocking() -> None:
    channel = MagicMock()
    publish_config_changed_blocking(
        channel,
        exchange_name="stream_helper",
        module_id="rule-bot",
        config_file="bot_responses.json",
        profile_id="default",
    )
    assert channel.basic_publish.called
    call_kwargs = channel.basic_publish.call_args.kwargs
    assert call_kwargs["routing_key"] == TOPIC_CONFIG_CHANGED
    body = call_kwargs["body"].decode("utf-8")
    assert "rule-bot" in body
    assert "bot_responses.json" in body


@patch("control.publisher.connect_blocking")
def test_try_publish_config_changed_success(mock_connect: MagicMock) -> None:
    connection = MagicMock()
    connection.is_open = True
    channel = MagicMock()
    connection.channel.return_value = channel
    mock_connect.return_value = connection

    assert try_publish_config_changed(module_id="llm-bot", config_file="llm_subscriber.json")
    connection.close.assert_called_once()


@patch("control.publisher.connect_blocking", side_effect=OSError("refused"))
def test_try_publish_config_changed_failure(_mock_connect: MagicMock) -> None:
    assert not try_publish_config_changed(module_id="llm-bot", config_file="llm_subscriber.json")
