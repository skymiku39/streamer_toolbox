"""子程序監控：parent 異常退出時一併終止子 process。"""

from __future__ import annotations

import atexit
import subprocess
import sys

_children: list[subprocess.Popen[str]] = []
_atexit_registered = False
_job_handle: int | None = None


def _init_windows_job() -> int | None:
    if sys.platform != "win32":
        return None

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        kernel32.CloseHandle(job)
        return None
    return job


def _assign_windows_job(process: subprocess.Popen[str]) -> None:
    global _job_handle
    if sys.platform != "win32" or process.poll() is not None:
        return
    if _job_handle is None:
        _job_handle = _init_windows_job()
    if not _job_handle:
        return
    import ctypes

    ctypes.windll.kernel32.AssignProcessToJobObject(_job_handle, int(process._handle))


def _linux_parent_death_signal() -> None:
    import ctypes

    libc = ctypes.CDLL("libc.so.6")
    libc.prctl(1, 15)  # PR_SET_PDEATHSIG → SIGTERM


def popen_preexec_fn() -> None | object:
    if sys.platform == "linux":
        return _linux_parent_death_signal
    return None


def track_child(process: subprocess.Popen[str]) -> None:
    global _atexit_registered
    _children.append(process)
    _assign_windows_job(process)
    if not _atexit_registered:
        atexit.register(terminate_tracked_children)
        _atexit_registered = True


def terminate_tracked_children() -> None:
    for process in list(_children):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    _children.clear()
