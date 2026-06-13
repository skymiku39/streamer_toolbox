# 知識庫範本

將此目錄的 `{TWITCH_CHANNEL}.md` 複製到 `data/knowledge/`（執行 `scripts/setup_knowledge.ps1` 可自動完成）。

Chroma 會在 `sub-llm` 啟動時 preload 一次，並以 fingerprint 避免重複 upsert。

## 檔案格式

- 使用 `##` 分段，每段會成為一個向量片段
- 建議內容：直播時間、常用梗、VIP、遊戲設定、禁止事項等
