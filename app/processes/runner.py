import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterable

from app.processes.base import ProcessSpec

SHUTDOWN_TIMEOUT_SECONDS = 10
POLL_INTERVAL_SECONDS = 0.2


def _prefix_stream(stream, prefix: str, output) -> None:
    for line in iter(stream.readline, ""):
        output.write(f"[{prefix}] {line}")
        output.flush()
    stream.close()


def run_processes(specs: Iterable[ProcessSpec]) -> int:
    specs = list(specs)
    if not specs:
        print("No processes to run.", file=sys.stderr)
        return 1

    processes: list[tuple[ProcessSpec, subprocess.Popen[str]]] = []
    shutdown_requested = False

    def shutdown(signum: int | None = None, frame: object | None = None) -> None:
        nonlocal shutdown_requested
        if shutdown_requested:
            return
        shutdown_requested = True
        for spec, process in processes:
            if process.poll() is None:
                print(f"[runner] Stopping {spec.name}...", file=sys.stderr)
                process.terminate()
        for _, process in processes:
            try:
                process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    for spec in specs:
        process = subprocess.Popen(
            [sys.executable, "-m", spec.module],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        processes.append((spec, process))
        thread = threading.Thread(
            target=_prefix_stream,
            args=(process.stdout, spec.name, sys.stdout),
            daemon=True,
        )
        thread.start()

    exit_code = 0
    while processes:
        if shutdown_requested:
            for _, process in processes:
                try:
                    process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    process.kill()
            break

        for spec, process in list(processes):
            return_code = process.poll()
            if return_code is None:
                continue
            if return_code != 0:
                print(
                    f"[runner] Process {spec.name} exited with code {return_code}",
                    file=sys.stderr,
                )
                exit_code = return_code
                shutdown()
            processes.remove((spec, process))

        if processes:
            time.sleep(POLL_INTERVAL_SECONDS)

    for _, process in processes:
        process.wait()

    return exit_code
