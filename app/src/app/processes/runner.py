import queue
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable

from app.console_encoding import configure_utf8_stdio, write_stdio
from app.processes.base import ProcessSpec
from app.processes.chat_ingress import (
    CHAT_FALLBACK_EXIT_CODE,
    CHAT_INGRESS_EVENTSUB,
    CHAT_INGRESS_IRC_FALLBACK,
    CHAT_INGRESS_STARTUP_TIMEOUT_SECONDS,
    EVENTSUB_PROCESS,
    IRC_FALLBACK_PROCESS,
    parse_chat_ingress_status,
)
from app.processes.child_supervisor import popen_preexec_fn, track_child, terminate_tracked_children
from app.processes.process_lock import locked_names, release, stop_all_command_hint
from app.processes.python_exec import subprocess_python_env, subprocess_python_executable
from app.processes.registry import registry

SHUTDOWN_TIMEOUT_SECONDS = 10
POLL_INTERVAL_SECONDS = 0.2

LineCallback = Callable[[str, str], None]


def _prefix_stream(
    stream,
    prefix: str,
    output,
    *,
    on_line: LineCallback | None = None,
) -> None:
    for line in iter(stream.readline, ""):
        if on_line is not None:
            on_line(prefix, line)
        write_stdio(f"[{prefix}] {line}", stream=output)
    stream.close()


def _start_process(
    spec: ProcessSpec,
    *,
    on_line: LineCallback | None = None,
) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        [subprocess_python_executable(), "-m", spec.module],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=subprocess_python_env(),
        preexec_fn=popen_preexec_fn(),
    )
    track_child(process)
    thread = threading.Thread(
        target=_prefix_stream,
        args=(process.stdout, spec.name, sys.stdout),
        kwargs={"on_line": on_line},
        daemon=True,
    )
    thread.start()
    return process


def _split_chat_ingress_specs(
    specs: list[ProcessSpec],
    *,
    chat_fallback: bool,
) -> tuple[list[ProcessSpec], ProcessSpec | None, ProcessSpec | None]:
    has_eventsub = any(spec.name == EVENTSUB_PROCESS for spec in specs)
    if not chat_fallback or not has_eventsub:
        return specs, None, None

    eventsub_spec = next(spec for spec in specs if spec.name == EVENTSUB_PROCESS)
    fallback_spec = next((spec for spec in specs if spec.name == IRC_FALLBACK_PROCESS), None)
    if fallback_spec is None:
        fallback_spec = registry.get(IRC_FALLBACK_PROCESS)

    remaining = [
        spec
        for spec in specs
        if spec.name not in {EVENTSUB_PROCESS, IRC_FALLBACK_PROCESS}
    ]
    return remaining, eventsub_spec, fallback_spec


def _supervise_eventsub_startup(
    eventsub_spec: ProcessSpec,
    fallback_spec: ProcessSpec,
    *,
    status_queue: queue.Queue[str],
    shutdown_requested: Callable[[], bool],
) -> tuple[subprocess.Popen[str] | None, subprocess.Popen[str] | None, int]:
    """啟動 EventSub ingress；必要時改啟 IRC fallback。回傳 (eventsub, fallback, exit_code)。"""
    process = _start_process(
        eventsub_spec,
        on_line=lambda _prefix, line: _enqueue_chat_status(status_queue, line),
    )
    deadline = time.time() + CHAT_INGRESS_STARTUP_TIMEOUT_SECONDS

    while time.time() < deadline:
        if shutdown_requested():
            process.terminate()
            return process, None, 0

        return_code = process.poll()
        if return_code is not None:
            if return_code == CHAT_FALLBACK_EXIT_CODE:
                print(
                    f"[runner] {eventsub_spec.name} chat read unavailable; "
                    f"starting {fallback_spec.name}",
                    file=sys.stderr,
                )
                return None, _start_process(fallback_spec), 0
            return process, None, return_code

        try:
            status = status_queue.get(timeout=POLL_INTERVAL_SECONDS)
        except queue.Empty:
            continue

        if status == CHAT_INGRESS_EVENTSUB:
            return process, None, 0
        if status == CHAT_INGRESS_IRC_FALLBACK:
            print(
                f"[runner] {eventsub_spec.name} requested IRC fallback; "
                f"starting {fallback_spec.name}",
                file=sys.stderr,
            )
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    process.kill()
            return None, _start_process(fallback_spec), 0

    print(
        f"[runner] Timed out waiting for {eventsub_spec.name} chat ingress status",
        file=sys.stderr,
    )
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
    return process, None, 1


def _enqueue_chat_status(status_queue: queue.Queue[str], line: str) -> None:
    status = parse_chat_ingress_status(line)
    if status is not None:
        status_queue.put(status)


def run_processes(
    specs: Iterable[ProcessSpec],
    *,
    chat_fallback: bool = False,
) -> int:
    configure_utf8_stdio()
    specs = list(specs)
    if not specs:
        print("No processes to run.", file=sys.stderr)
        return 1

    remaining_specs, eventsub_spec, fallback_spec = _split_chat_ingress_specs(
        specs,
        chat_fallback=chat_fallback,
    )

    planned_specs: list[ProcessSpec] = list(remaining_specs)
    if eventsub_spec is not None:
        planned_specs.append(eventsub_spec)
    if fallback_spec is not None:
        planned_specs.append(fallback_spec)
    already_running = locked_names([spec.name for spec in planned_specs])
    if already_running:
        print(
            "[runner] 以下 process 已在執行中，請先停止後再啟動："
            f" {', '.join(already_running)}",
            file=sys.stderr,
        )
        print(
            f"[runner] 可執行：{stop_all_command_hint()}",
            file=sys.stderr,
        )
        return 1

    processes: list[tuple[ProcessSpec, subprocess.Popen[str]]] = []
    shutdown_requested = False
    exit_code = 0

    def shutdown(signum: int | None = None, frame: object | None = None) -> None:
        nonlocal shutdown_requested
        if shutdown_requested:
            return
        shutdown_requested = True
        for spec, process in processes:
            if process.poll() is None:
                print(f"[runner] Stopping {spec.name}...", file=sys.stderr)
                process.terminate()
        for spec, process in processes:
            try:
                process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
            release(spec.name)
        terminate_tracked_children()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if eventsub_spec is not None and fallback_spec is not None:
        status_queue: queue.Queue[str] = queue.Queue()
        eventsub_process, fallback_process, startup_code = _supervise_eventsub_startup(
            eventsub_spec,
            fallback_spec,
            status_queue=status_queue,
            shutdown_requested=lambda: shutdown_requested,
        )
        if startup_code != 0:
            shutdown()
            return startup_code
        if eventsub_process is not None:
            processes.append((eventsub_spec, eventsub_process))
        if fallback_process is not None:
            processes.append((fallback_spec, fallback_process))

    for spec in remaining_specs:
        try:
            processes.append((spec, _start_process(spec)))
        except RuntimeError as exc:
            print(f"[runner] {exc}", file=sys.stderr)
            shutdown()
            return 1

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
            release(spec.name)
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
