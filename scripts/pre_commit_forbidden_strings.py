"""Pre-commit hook: block staging files that contain retired commit-message wording."""
from __future__ import annotations

import sys

# 以 unicode escape 組合，避免在 repo 原始碼留下字面文字
_FORBIDDEN = "\u81ea\u52d5\u63d0\u4ea4"


def main(argv: list[str]) -> int:
    blocked: list[str] = []
    for path in argv[1:]:
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError as exc:
            print(f"Cannot read {path}: {exc}", file=sys.stderr)
            return 1
        if _FORBIDDEN in text:
            blocked.append(path)

    if blocked:
        print("Blocked staging files that contain retired wording:", file=sys.stderr)
        for path in blocked:
            print(f"  - {path}", file=sys.stderr)
        print(
            "Use commit format: type: emoji [AI] subject (see .cursor/rules/git-commit.mdc)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
