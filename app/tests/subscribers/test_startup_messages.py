from sub_llm.openai_client import LlmApiError
from sub_llm.startup_messages import build_degraded_startup_announcement


def test_build_degraded_startup_announcement_missing_credential() -> None:
    message = build_degraded_startup_announcement(
        channel="demo",
        backend="gemini",
        error=ValueError("GOOGLE_AI_API_KEY is required"),
    )
    assert "憑證" in message
    assert "Gemini" in message


def test_build_degraded_startup_announcement_network_error() -> None:
    message = build_degraded_startup_announcement(
        channel="demo",
        backend="gemini",
        error=LlmApiError("LLM API network error: timed out"),
    )
    assert "連線" in message or "Network" in message
    assert "降級模式" in message
