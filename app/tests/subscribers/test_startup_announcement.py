from __future__ import annotations

from events import TOPIC_CHAT_REPLY
from safety import PassThroughSafetyFilter

from sub_llm.config import LlmSubscriberConfig
from sub_llm.llm import TemplateLlmClient
from sub_llm.startup_announcement import (
    publish_startup_announcement,
    resolve_announcement_channel,
    startup_announcement_enabled,
)
from sub_llm.openai_client import LlmApiError


def test_startup_announcement_enabled_defaults_true(monkeypatch) -> None:
    monkeypatch.delenv("LLM_STARTUP_ANNOUNCEMENT", raising=False)
    assert startup_announcement_enabled() is True


def test_startup_announcement_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("LLM_STARTUP_ANNOUNCEMENT", "false")
    assert startup_announcement_enabled() is False


def test_resolve_announcement_channel_strips_hash(monkeypatch) -> None:
    monkeypatch.setenv("TWITCH_CHANNEL", "#skymiku39")
    assert resolve_announcement_channel() == "skymiku39"


def test_publish_startup_announcement_publishes_chat_reply(monkeypatch) -> None:
    monkeypatch.setenv("TWITCH_CHANNEL", "skymiku39")
    monkeypatch.setenv("LLM_STARTUP_ANNOUNCEMENT", "true")
    published: list[tuple[str, dict]] = []

    def capture(topic: str, payload: dict) -> None:
        published.append((topic, payload))

    ok = publish_startup_announcement(
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        config=LlmSubscriberConfig(trigger_prefixes=["!ask"]),
        publish=capture,
    )

    assert ok is True
    assert len(published) == 1
    topic, payload = published[0]
    assert topic == TOPIC_CHAT_REPLY
    assert payload["channel"] == "skymiku39"
    assert payload["content"]
    assert "skymiku39" in payload["content"]
    assert "Template" in payload["content"]
    assert "LLM" in payload["content"]


def test_publish_startup_announcement_falls_back_on_llm_failure(monkeypatch) -> None:
    monkeypatch.setenv("TWITCH_CHANNEL", "skymiku39")
    published: list[tuple[str, dict]] = []

    class FailingLlm:
        def generate_startup_greeting(self, *, channel: str, trigger_prefixes: tuple[str, ...]) -> str:
            raise LlmApiError("LLM API network error: timed out")

    ok = publish_startup_announcement(
        llm=FailingLlm(),
        safety=PassThroughSafetyFilter(),
        config=LlmSubscriberConfig(),
        publish=lambda topic, payload: published.append((topic, payload)),
        backend="gemini",
    )

    assert ok is True
    assert len(published) == 1
    content = published[0][1]["content"]
    assert "降級模式" in content
    assert "Degraded Mode" in content
    assert "推理端點" in content
    assert "Network" in content or "連線" in content


def test_publish_startup_announcement_skips_without_channel(monkeypatch) -> None:
    monkeypatch.delenv("TWITCH_CHANNEL", raising=False)
    published: list[tuple[str, dict]] = []

    ok = publish_startup_announcement(
        llm=TemplateLlmClient(),
        safety=PassThroughSafetyFilter(),
        config=LlmSubscriberConfig(),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    assert ok is False
    assert published == []
