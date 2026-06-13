from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pre_commit_commit_msg",
    Path(__file__).resolve().parents[2] / "scripts" / "pre_commit_commit_msg.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate_commit_message = _mod.validate_commit_message
is_legacy_subject_prefix = _mod.is_legacy_subject_prefix
_legacy_subject = _mod._LEGACY_SUBJECT_PREFIX


def test_rejects_legacy_subject_prefix() -> None:
    error = validate_commit_message(f"{_legacy_subject} 新增功能")
    assert error is not None
    assert "type: emoji [AI] subject" in error


def test_detects_legacy_subject_prefix() -> None:
    assert is_legacy_subject_prefix(f"{_legacy_subject} 新增功能")


def test_accepts_conventional_format() -> None:
    assert validate_commit_message("feat: ✨ [AI] 新增 OAuth 登入流程") is None


def test_accepts_message_with_body() -> None:
    message = "fix: 🐛 [AI] 修正空行導致解析失敗\n\n補充說明。"
    assert validate_commit_message(message) is None


def test_rejects_wrong_emoji_for_type() -> None:
    error = validate_commit_message("feat: 🐛 [AI] 標題錯誤")
    assert error is not None
    assert "應搭配 emoji" in error


def test_rejects_unknown_type() -> None:
    error = validate_commit_message("wip: ✨ [AI] 未完成")
    assert error is not None
    assert "不支援的 type" in error


def test_skips_merge_commits() -> None:
    assert validate_commit_message("Merge branch 'main' into feature") is None
