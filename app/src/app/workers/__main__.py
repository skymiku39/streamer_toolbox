from __future__ import annotations

import argparse
import os
import sys
import time

from dotenv import load_dotenv

from app.console_encoding import configure_utf8_stdio
from app.module_paths import ensure_legacy_module_paths

ensure_legacy_module_paths()
configure_utf8_stdio()

from app.workers.memory_config import MemoryWorkerConfig
from app.workers.memory_summarizer import create_summarizer
from app.workers.memory_worker import MemoryWorker
from stream_store import StreamTextStore

PROCESS_NAME = "sub-memory-worker"


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
        "--db-path",
        default=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=int(os.environ.get("MEMORY_INTERVAL_MINUTES", "5")),
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
        "--llm-backend",
        default=os.environ.get("MEMORY_LLM_BACKEND", "template"),
        choices=["template", "openai", "gemini"],
    )
    args = parser.parse_args(argv)

    config = MemoryWorkerConfig.from_env()
    session_id = (args.session_id or config.session_id or "").strip() or None
    config = MemoryWorkerConfig(
        db_path=args.db_path,
        session_id=session_id,
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

    store = StreamTextStore(config.db_path)
    worker = MemoryWorker(store, config, summarizer)

    print(
        f"{PROCESS_NAME} db={config.db_path} session={config.session_id or '(auto)'} "
        f"mode={config.record_mode} interval={config.interval_minutes}m "
        f"backend={config.llm_backend}",
        file=sys.stderr,
        flush=True,
    )

    try:
        if args.until_empty:
            while worker.run_once():
                pass
            return 0
        if args.once:
            worker.run_once()
            return 0

        interval_sec = max(1, config.interval_minutes) * 60
        while True:
            worker.run_once()
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("Shutting down...", file=sys.stderr)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
