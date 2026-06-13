from __future__ import annotations

import subprocess
import sys

from app.processes.child_supervisor import popen_preexec_fn, track_child, terminate_tracked_children


def test_popen_preexec_fn_is_none_on_windows() -> None:
    if sys.platform == "win32":
        assert popen_preexec_fn() is None


def test_track_and_terminate_children() -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        preexec_fn=popen_preexec_fn(),
    )
    track_child(process)
    assert process.poll() is None
    terminate_tracked_children()
    assert process.poll() is not None
