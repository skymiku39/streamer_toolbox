from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from app.console_encoding import configure_utf8_stdio
from app.module_paths import ensure_legacy_module_paths

ensure_legacy_module_paths()

configure_utf8_stdio()



from app.llm_tiers import LlmTier, resolve_tier
from app.publishing.summary_publisher import create_summary_publisher
from app.workers.memory_config import DEFAULT_MEMORY_INTERVAL_MINUTES, MemoryWorkerConfig
from app.workers.memory_scheduler import run_scheduled_worker
from app.workers.memory_summarizer import create_summarizer
from app.workers.memory_trigger import (
    MemoryTriggerHandle,
    MemoryTriggerListener,
    publish_memory_summarize_trigger,
)
from app.workers.memory_worker import MemoryWorker
from stream_store import StreamTextStore

PROCESS_NAME = "sub-memory-worker"





def _env_bool(name: str, default: bool) -> bool:

    raw = os.environ.get(name, "").strip().lower()

    if not raw:

        return default

    return raw in {"1", "true", "yes", "on"}





def main(argv: list[str] | None = None) -> int:

    load_dotenv(override=True)

    parser = argparse.ArgumentParser(

        description="Periodic chat summarization → summaries table (Phase 1)",

    )

    parser.add_argument(

        "--session-id",

        default=None,

        help="Override STREAM_SESSION_ID for this run",

    )

    parser.add_argument(

        "--channel",

        default=None,

        help="Override TWITCH_CHANNEL / MEMORY_CHANNEL for session resolution",

    )

    parser.add_argument(

        "--db-path",

        default=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),

    )

    parser.add_argument(

        "--interval-minutes",

        type=int,

        default=int(

            os.environ.get("MEMORY_INTERVAL_MINUTES", str(DEFAULT_MEMORY_INTERVAL_MINUTES))

        ),

    )

    parser.add_argument(

        "--once",

        action="store_true",

        help="Run one summarization cycle and exit",

    )

    parser.add_argument(

        "--until-empty",

        action="store_true",

        help="Run cycles until no unsummarized records remain",

    )

    parser.add_argument(

        "--trigger",

        action="store_true",

        help="Publish memory.summarize.request to MQ and exit",

    )

    parser.add_argument(

        "--no-trigger-listen",

        action="store_true",

        help="Disable MQ trigger listener (timer-only mode)",

    )

    parser.add_argument(

        "--llm-backend",

        default=os.environ.get("MEMORY_LLM_BACKEND", "template"),

        choices=["template", "openai", "gemini"],

    )

    args = parser.parse_args(argv)



    config = MemoryWorkerConfig.from_env()

    session_id = (args.session_id or config.session_id or "").strip() or None



    if args.trigger:

        try:

            publish_memory_summarize_trigger(session_id=session_id, source="cli")

        except Exception as exc:

            print(str(exc), file=sys.stderr)

            return 1

        return 0



    from app.processes.process_lock import acquire_process_lock

    with acquire_process_lock(PROCESS_NAME):
        config = MemoryWorkerConfig(
            db_path=args.db_path,
            session_id=session_id,
            channel=(args.channel or config.channel or "").strip() or None,
            interval_minutes=args.interval_minutes,
            llm_backend=args.llm_backend,
            batch_limit=config.batch_limit,
            record_mode=config.record_mode,
        )

        try:
            summarizer = create_summarizer(config.llm_backend)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        tier_log = ""
        if config.llm_backend in {"openai", "gemini"}:
            tier = resolve_tier(LlmTier.MEMORY, memory_backend=config.llm_backend)
            tier_log = f" {tier.log_label()}"

        store = StreamTextStore(config.db_path)
        worker = MemoryWorker(
            store,
            config,
            summarizer,
            summary_publisher=create_summary_publisher(),
        )
        trigger_listen = not args.no_trigger_listen and _env_bool("MEMORY_TRIGGER_LISTEN", True)

        print(
            f"{PROCESS_NAME} db={config.db_path} session={config.session_id or '(auto)'} "
            f"mode={config.record_mode} interval={config.interval_minutes}m "
            f"backend={config.llm_backend} trigger_listen={trigger_listen}{tier_log}",
            file=sys.stderr,
            flush=True,
        )

        trigger_handle = MemoryTriggerHandle()
        listener: MemoryTriggerListener | None = None
        if trigger_listen and not args.once and not args.until_empty:
            listener = MemoryTriggerListener(trigger_handle)
            listener.start()

        try:
            if args.until_empty:
                while worker.run_once():
                    pass
                return 0
            if args.once:
                worker.run_once()
                return 0

            interval_sec = max(1, config.interval_minutes) * 60
            run_scheduled_worker(worker, trigger_handle, interval_sec=interval_sec)
        except KeyboardInterrupt:
            print("Shutting down...", file=sys.stderr)
        finally:
            store.close()
        return 0



if __name__ == "__main__":

    raise SystemExit(main())

