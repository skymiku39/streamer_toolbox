import argparse
import sys

from dotenv import load_dotenv

from app.console_encoding import configure_utf8_stdio
from app.module_paths import ensure_legacy_module_paths

ensure_legacy_module_paths()
configure_utf8_stdio()

from app.processes.registry import registry
from app.processes.runner import run_processes
from app.processes.stacks import PROCESS_STACKS, resolve_stack
from app.publishers import discover_publishers
from app.subscribers import discover_subscribers

discover_publishers()
discover_subscribers()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="streamer-toolbox process manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List registered publishers and subscribers")

    run_parser = subparsers.add_parser("run", help="Run one or more registered processes")
    run_parser.add_argument(
        "names",
        nargs="*",
        help="Process names (default: all registered processes)",
    )
    run_parser.add_argument(
        "--chat-fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "When ingress-twitch-eventsub is included, fall back to ingress-ttv-read "
            "if EventSub chat read is unavailable (default: enabled)"
        ),
    )
    group = run_parser.add_mutually_exclusive_group()
    group.add_argument("--publishers", action="store_true", help="Run all publishers")
    group.add_argument("--subscribers", action="store_true", help="Run all subscribers")
    stack_names = ", ".join(sorted(PROCESS_STACKS))
    group.add_argument(
        "--stack",
        choices=sorted(PROCESS_STACKS),
        help=f"Run a predefined process set ({stack_names})",
    )

    return parser


def cmd_list() -> int:
    publishers = registry.all_publishers()
    subscribers = registry.all_subscribers()

    print("Publishers:")
    for spec in publishers:
        print(f"  {spec.name:<22} {spec.description}")
    if not publishers:
        print("  (none)")

    print()
    print("Subscribers:")
    for spec in subscribers:
        print(f"  {spec.name:<22} {spec.description}")
    if not subscribers:
        print("  (none)")

    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if args.stack:
        try:
            names = resolve_stack(args.stack)
        except KeyError as exc:
            print(exc, file=sys.stderr)
            return 1
    elif args.publishers:
        specs = registry.all_publishers()
        return run_processes(specs, chat_fallback=args.chat_fallback)
    elif args.subscribers:
        specs = registry.all_subscribers()
        return run_processes(specs, chat_fallback=args.chat_fallback)
    elif args.names:
        names = list(args.names)
    else:
        specs = registry.all_processes()
        return run_processes(specs, chat_fallback=args.chat_fallback)

    try:
        specs = registry.resolve(names)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.stack == "llm":
        print(
            "[runner] 提示：sub-llm 需搭配終端 1 執行 "
            "`uv run python -m app.main run --stack ingress` "
            "才會收到 stream.metadata（標題／遊戲）。",
            file=sys.stderr,
        )

    if not specs:
        print("No matching processes found.", file=sys.stderr)
        return 1

    return run_processes(specs, chat_fallback=args.chat_fallback)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        return cmd_list()
    if args.command == "run":
        return cmd_run(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
