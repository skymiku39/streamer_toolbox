from __future__ import annotations

import json

import pytest

from sub_llm.observability import log_event, log_llm_messages


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


def test_log_llm_messages_multiline_format(capsys: pytest.CaptureFixture[str]) -> None:
    log_llm_messages(
        [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "問題:你好"},
        ],
        purpose="ask",
    )
    err = capsys.readouterr().err
    assert "[sub-llm] llm_prompt purpose=ask" in err
    assert "[system]" in err
    assert "你是助手" in err
    assert "[user]" in err
    assert "問題:你好" in err
    assert "[sub-llm] llm_prompt end purpose=ask" in err


def test_log_llm_messages_json_mode(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_LOG_JSON", "true")
    log_llm_messages([{"role": "user", "content": "問題"}], purpose="ask")
    err = capsys.readouterr().err.strip()
    payload = json.loads(err[len("[sub-llm] ") :])
    assert payload["event"] == "llm_prompt"
    assert payload["purpose"] == "ask"
    assert payload["messages"][0]["content"] == "問題"


def test_log_llm_messages_can_disable(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_LOG_PROMPT", "0")
    log_llm_messages([{"role": "user", "content": "問題"}], purpose="ask")
    assert capsys.readouterr().err == ""


def test_log_llm_messages_truncates_when_configured(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_LOG_PROMPT_MAX_CHARS", "5")
    log_llm_messages([{"role": "user", "content": "一二三四五六"}], purpose="ask")
    err = capsys.readouterr().err
    assert "一二三四五" in err
    assert "truncated, total 6 chars" in err
