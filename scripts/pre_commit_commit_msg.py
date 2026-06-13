"""Pre-commit commit-msg hook: enforce Conventional Commits + [AI] format."""
from __future__ import annotations

import re
import sys
from pathlib import Path

TYPE_EMOJI: dict[str, str] = {
    "feat": "✨",
    "fix": "🐛",
    "perf": "⚡️",
    "test": "✅",
    "docs": "📝",
    "refactor": "♻️",
    "style": "💄",
    "revert": "🔙",
    "build": "📦",
    "ci": "👷",
    "chore": "⚙️",
}

# 舊式 commit 前綴（以 unicode escape 避免在原始碼出現字面文字）
_LEGACY_SUBJECT_PREFIX = "[" + "AI " + "\u81ea\u52d5\u63d0\u4ea4" + "]"

SUBJECT_PATTERN = re.compile(
    r"^(?P<type>[a-z]+): (?P<emoji>.+?) \[AI\] (?P<subject>.+)$"
)

SKIP_PREFIXES = (
    "Merge ",
    "Revert ",
    "fixup!",
    "squash!",
)


def subject_line(message: str) -> str:
    for line in message.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def is_legacy_subject_prefix(subject: str) -> bool:
    return subject.startswith(_LEGACY_SUBJECT_PREFIX)


def validate_commit_message(message: str) -> str | None:
    """Return an error string when invalid; None when valid or skipped."""
    subject = subject_line(message)
    if not subject:
        return "commit 訊息不可為空"
    if any(subject.startswith(prefix) for prefix in SKIP_PREFIXES):
        return None
    if is_legacy_subject_prefix(subject):
        return (
            "commit 主旨須為 type: emoji [AI] subject；"
            "請見 .cursor/rules/git-commit.mdc"
        )

    match = SUBJECT_PATTERN.match(subject)
    if match is None:
        return (
            "commit 主旨格式須為 type: emoji [AI] subject；"
            "範例：feat: ✨ [AI] 新增 OAuth 登入流程"
        )

    commit_type = match.group("type")
    expected_emoji = TYPE_EMOJI.get(commit_type)
    if expected_emoji is None:
        allowed = ", ".join(sorted(TYPE_EMOJI))
        return f"不支援的 type: {commit_type!r}（允許：{allowed}）"

    if match.group("emoji") != expected_emoji:
        return (
            f"type {commit_type!r} 應搭配 emoji {expected_emoji!r}，"
            f"目前為 {match.group('emoji')!r}"
        )

    if not match.group("subject").strip():
        return "subject 不可為空"
    return None


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: pre_commit_commit_msg.py <commit-msg-file>", file=sys.stderr)
        return 1

    message = Path(argv[1]).read_text(encoding="utf-8")
    error = validate_commit_message(message)
    if error is None:
        return 0

    print("Invalid commit message:", file=sys.stderr)
    print(f"  {error}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Expected format:", file=sys.stderr)
    print("  type: emoji [AI] subject", file=sys.stderr)
    print("Example:", file=sys.stderr)
    print("  feat: ✨ [AI] 新增 OAuth 登入流程", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
