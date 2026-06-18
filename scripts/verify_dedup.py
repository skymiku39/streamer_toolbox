"""跨 process 驗證 IdempotencyStore（Windows 可用）。

勿使用 ``python -c`` + ``multiprocessing.Pool``：Windows spawn 無法 pickle
``__main__`` 內定義的 worker，會出現 ``Can't get attribute 'ingress_worker'``。
本腳本改以獨立 subprocess 競爭 claim，與實際多開 process 行為一致。
"""

from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "_verify_dedup.db"
MSG = "a07e5748-test-dedup"

CLAIM_SNIPPET = """
from stream_store.idempotency import IdempotencyStore
import sys
store = IdempotencyStore({db!r})
ok = store.claim({namespace!r}, {key!r})
store.close()
sys.stdout.write("1" if ok else "0")
"""


def log(message: str, data: dict) -> None:
    print(f"  {message}: {data}", file=sys.stderr)


def spawn_claim(namespace: str, key: str) -> bool:
    code = CLAIM_SNIPPET.format(db=str(DB), namespace=namespace, key=key)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout.strip() == "1"


def verify_layer(name: str, namespace: str, key: str, workers: int = 3) -> int:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(spawn_claim, namespace, key) for _ in range(workers)]
        results = [future.result() for future in as_completed(futures)]
    wins = sum(1 for item in results if item)
    log(f"{name} parallel claim", {"results": results, "wins": wins})
    return wins


def main() -> int:
    if DB.exists():
        DB.unlink()

    layers = [
        ("ingress", "ingress.chat.message", MSG),
        ("sub_llm", "sub_llm.chat.trigger", MSG),
        ("connector", "twitch_connector.chat.reply", f"logic-llm:{MSG}"),
    ]

    for name, namespace, key in layers:
        wins = verify_layer(name, namespace, key)
        if wins != 1:
            print(f"VERIFICATION_FAIL layer={name} wins={wins}", file=sys.stderr)
            return 1

    print("VERIFICATION_PASS wins_per_layer=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
