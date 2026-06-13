"""驗證 Chroma 知識庫 preload 與查詢（讀取 .env）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [
    str(ROOT / "app" / "src"),
    str(ROOT / "app" / "src" / "app" / "subscribers"),
]

load_dotenv(ROOT / ".env")

from sub_llm.factory import create_knowledge_store, preload_knowledge_store  # noqa: E402


def main() -> int:
    knowledge_path = (ROOT / "data" / "knowledge").resolve()
    if not any(knowledge_path.glob("*.md")):
        print("找不到知識庫檔案，請先執行 scripts/setup_knowledge.ps1", file=sys.stderr)
        return 1

    os.environ["LLM_MEMORY_FROM_DB"] = "false"
    os.environ["LLM_KNOWLEDGE_BACKEND"] = "chroma"
    os.environ["LLM_KNOWLEDGE_PATH"] = str(knowledge_path)
    os.environ.setdefault("LLM_CHROMA_DIR", str(ROOT / "data" / "chroma"))

    store = create_knowledge_store(str(knowledge_path))
    preload_knowledge_store(store)
    chroma_snippet = store.query("777 幸運數字")
    if chroma_snippet:
        print("[chroma]")
        print(chroma_snippet[:500])
        return 0

    print("[chroma] 查詢無結果", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
