import argparse
import sys

from dotenv import load_dotenv

from app.processes.bootstrap import register_builtin_processes
from app.processes.registry import registry
from app.processes.runner import run_processes

register_builtin_processes()


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
    if args.publishers:
        specs = registry.all_publishers()
    elif args.subscribers:
        specs = registry.all_subscribers()
    elif args.names:
        try:
            specs = registry.resolve(args.names)
        except KeyError as exc:
            print(exc, file=sys.stderr)
            return 1
    else:
        specs = registry.all_processes()

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
