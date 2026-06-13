from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pre_commit_forbidden_strings",
    Path(__file__).resolve().parents[2] / "scripts" / "pre_commit_forbidden_strings.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_forbidden = _mod._FORBIDDEN


def test_blocks_file_containing_forbidden_wording(tmp_path: Path) -> None:
    bad_file = tmp_path / "note.md"
    bad_file.write_text(f"[AI {_forbidden}]", encoding="utf-8")
    script = Path(__file__).resolve().parents[2] / "scripts" / "pre_commit_forbidden_strings.py"
    result = subprocess.run(
        [sys.executable, str(script), str(bad_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1


def test_allows_clean_file(tmp_path: Path) -> None:
    good_file = tmp_path / "note.md"
    good_file.write_text("feat: ✨ [AI] 範例", encoding="utf-8")
    script = Path(__file__).resolve().parents[2] / "scripts" / "pre_commit_forbidden_strings.py"
    result = subprocess.run(
        [sys.executable, str(script), str(good_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
