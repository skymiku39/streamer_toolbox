# 知識庫範本

將此目錄的 `{TWITCH_CHANNEL}.md` 複製到 `data/knowledge/`（執行 `scripts/setup_knowledge.ps1` 可自動完成，**僅在目標不存在時複製**）。

Chroma 會在 `sub-llm` 啟動時 preload 一次，並以 fingerprint 避免重複 upsert。

## 知識 vs 記憶

| | **知識庫（本目錄）** | **記憶（L2 摘要）** |
|---|---------------------|---------------------|
| 檔案 | `data/knowledge/*.md` | `data/stream_text.db` → `summaries` |
| Chroma | `kb_global` | `kb_memory`（依 session） |
| 誰維護 | 你手動編輯 Markdown | `app.workers` 自動摘要 |
| 內容 | 規則、人設、梗、FAQ | 這場直播發生什麼 |
| 生命週期 | 跨場次、長期 | 以當日 session 為主 |

短期（最近數分鐘 STT + 聊天）在 `sub-llm` 程序內 buffer，**不用 RAG**，也無需寫入本目錄。

## 檔案格式

- 使用 `##` 分段，每段會成為 Chroma 的一個向量片段
- 建議段落：身份、指令、梗、VIP、回覆風格、禁止事項
- 勿把整場聊天或逐字稿貼進知識庫

## 更新流程

```powershell
# 首次
powershell -NoProfile -File scripts/setup_knowledge.ps1

# 編輯 data/knowledge/{頻道}.md 後驗證
uv run python scripts/verify_chroma_knowledge.py
uv run python scripts/verify_llm_prompt.py
```

若 `data/knowledge/` 已存在，`setup_knowledge.ps1` 不會覆寫；請直接編輯 `data/knowledge/` 或手動從本目錄複製合併。
