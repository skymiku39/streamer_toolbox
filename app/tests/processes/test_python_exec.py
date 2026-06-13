from __future__ import annotations

import os
import sys

from app.processes.python_exec import subprocess_python_executable


def test_subprocess_python_executable_prefers_base_when_shimmed() -> None:
    base = getattr(sys, "_base_executable", None)
    if (
        base
        and os.path.isfile(base)
        and os.path.normcase(os.path.abspath(base))
        != os.path.normcase(os.path.abspath(sys.executable))
    ):
        assert subprocess_python_executable() == base
    else:
        assert subprocess_python_executable() == sys.executable
