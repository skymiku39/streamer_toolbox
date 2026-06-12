from __future__ import annotations

import pytest

from app.console_encoding import configure_utf8_stdio, utf8_subprocess_env, write_stdio


def test_configure_utf8_stdio_does_not_raise() -> None:
    configure_utf8_stdio()


def test_utf8_subprocess_env_sets_flags() -> None:
    env = utf8_subprocess_env({})
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_write_stdio_roundtrip_utf8(capsys: pytest.CaptureFixture[str]) -> None:
    write_stdio("測試→箭頭\n")
    captured = capsys.readouterr()
    assert "測試" in captured.out
