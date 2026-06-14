from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "verify_setup",
    _ROOT / "scripts" / "verify_setup.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["verify_setup"] = _mod
_spec.loader.exec_module(_mod)

check_env_file = _mod.check_env_file
check_python_version = _mod.check_python_version
check_workspace_packages = _mod.check_workspace_packages
parse_env_channel = _mod.parse_env_channel
print_results = _mod.print_results


def test_check_python_version_accepts_current_runtime() -> None:
    result = check_python_version()
    assert result.ok is True
    assert result.name == "python_version"


def test_check_python_version_rejects_old_python(monkeypatch: pytest.MonkeyPatch) -> None:
    class OldVersion:
        major = 3
        minor = 10
        micro = 0

    monkeypatch.setattr(_mod.sys, "version_info", OldVersion())
    result = check_python_version()
    assert result.ok is False
    assert "3.11" in result.hint


def test_parse_env_channel_reads_value(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\nRABBITMQ_URL=amqp://guest:guest@127.0.0.1:5672/\n"
        'TWITCH_CHANNEL="my_channel"\n',
        encoding="utf-8",
    )
    assert parse_env_channel(env) == "my_channel"


def test_parse_env_channel_missing_returns_none(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("RABBITMQ_URL=amqp://guest:guest@127.0.0.1:5672/\n", encoding="utf-8")
    assert parse_env_channel(env) is None


def test_check_env_file_missing(tmp_path: Path) -> None:
    result = check_env_file(tmp_path)
    assert result.ok is False
    assert "找不到 .env" in result.detail


def test_check_env_file_rejects_placeholder_channel(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("TWITCH_CHANNEL=your_channel\n", encoding="utf-8")
    result = check_env_file(tmp_path)
    assert result.ok is False
    assert "範本值" in result.detail


def test_check_env_file_accepts_real_channel(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("TWITCH_CHANNEL=skymiku39\n", encoding="utf-8")
    result = check_env_file(tmp_path)
    assert result.ok is True
    assert "skymiku39" in result.detail


def test_check_workspace_packages_ok_when_vendored(tmp_path: Path) -> None:
    root = tmp_path / "streamer_toolbox"
    (root / "packages" / "ttvchat-lens" / "src" / "ttvchat_lens").mkdir(parents=True)
    (root / "packages" / "tubechat-lens" / "src" / "tubechat_lens").mkdir(parents=True)
    result = check_workspace_packages(root)
    assert result.ok is True


def test_check_workspace_packages_fail_when_missing(tmp_path: Path) -> None:
    root = tmp_path / "streamer_toolbox"
    root.mkdir()
    result = check_workspace_packages(root)
    assert result.ok is False
    assert "ttvchat-lens" in result.detail


def test_print_results_pass(capsys: pytest.CaptureFixture[str]) -> None:
    results = [_mod.CheckResult("demo", True, "ok")]
    code = print_results(results)
    captured = capsys.readouterr().out
    assert code == 0
    assert "SETUP_VERIFICATION_PASS" in captured


def test_print_results_fail(capsys: pytest.CaptureFixture[str]) -> None:
    results = [
        _mod.CheckResult("demo", False, "broken", hint="fix me"),
    ]
    code = print_results(results)
    captured = capsys.readouterr().out
    assert code == 1
    assert "SETUP_VERIFICATION_FAIL" in captured
    assert "fix me" in captured
