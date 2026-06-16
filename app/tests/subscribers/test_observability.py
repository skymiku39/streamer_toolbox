from __future__ import annotations

import json

import pytest

from sub_llm.observability import log_event


def test_log_event_key_value_format(capsys: pytest.CaptureFixture[str]) -> None:
    log_event("ask_decision", action="llm", latency_ms=42, llm_called=True)
    err = capsys.readouterr().err.strip()
    assert err.startswith("[sub-llm] ")
    assert "event=ask_decision" in err
    assert "action=llm" in err
    assert "latency_ms=42" in err
    assert "llm_called=true" in err


def test_log_event_omits_none_fields(capsys: pytest.CaptureFixture[str]) -> None:
    log_event("ask_decision", action="degraded", status=None)
    err = capsys.readouterr().err
    assert "status=" not in err
    assert "action=degraded" in err


def test_log_event_json_mode(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_LOG_JSON", "true")
    log_event("ask_decision", action="circuit_open", channel="demo")
    err = capsys.readouterr().err.strip()
    assert err.startswith("[sub-llm] ")
    payload = json.loads(err[len("[sub-llm] ") :])
    assert payload == {
        "event": "ask_decision",
        "action": "circuit_open",
        "channel": "demo",
    }
