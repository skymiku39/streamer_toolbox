from __future__ import annotations

from app.console_encoding import configure_utf8_stdio, utf8_subprocess_env


def test_configure_utf8_stdio_does_not_raise() -> None:
    configure_utf8_stdio()


def test_utf8_subprocess_env_sets_flags() -> None:
    env = utf8_subprocess_env({})
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"
