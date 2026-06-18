"""Pre-commit hook: block staging of runtime data, secrets, and token caches."""
from __future__ import annotations

import sys

BLOCKED_PREFIXES = ("data/", "logs/")
BLOCKED_EXACT = {".env", ".tio.tokens.json"}
BLOCKED_SUFFIXES = (".pem", ".db", ".jsonl")


def _is_root_debug_artifact(normalized: str) -> bool:
    """攔截 repo 根目錄的 debug 產物（debug-*.log / .json / .out 等）。"""
    return "/" not in normalized and normalized.startswith("debug-")


def main(argv: list[str]) -> int:
    blocked: list[str] = []
    for path in argv[1:]:
        normalized = path.replace("\\", "/")
        if normalized in BLOCKED_EXACT:
            blocked.append(path)
            continue
        if _is_root_debug_artifact(normalized):
            blocked.append(path)
            continue
        if any(normalized.startswith(prefix) for prefix in BLOCKED_PREFIXES):
            blocked.append(path)
            continue
        if normalized.endswith(BLOCKED_SUFFIXES) and not normalized.startswith("config/examples/"):
            blocked.append(path)

    if blocked:
        print("Blocked staging of runtime or secret files:")
        for path in blocked:
            print(f"  - {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
