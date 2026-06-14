# 營運者上手指南

本文件給**想實際跑直播 Bot、較少改程式**的使用者。若你要開發或修改模組，請改看 [development.md](development.md)。

整體流程：安裝 → 自動驗證 → 手動看聊天（Phase 01）→ 設定 OAuth 與 LLM → 雙終端跑 Bot。

## 前置需求

| 項目 | 說明 |
|------|------|
| 作業系統 | Windows 10+（本指南以 PowerShell 為主） |
| Python | 3.11 以上 |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Python 套件與虛擬環境管理 |
| Docker Desktop | 本地 RabbitMQ（`docker compose`） |
| Twitch 頻道 | 要收聽的頻道名稱（不含 `#`） |

## 第 0 層：一次性安裝

### 0.1 Clone 與安裝

本 repo 為**單一獨立專案**：Twitch / YouTube 聊天讀取已收編於 `packages/ttvchat-lens`、`packages/tubechat-lens`，**只需 clone `streamer_toolbox`**。

```powershell
git clone <你的 streamer_toolbox URL>
cd streamer_toolbox
uv sync
copy .env.example .env
```

編輯 `.env`，至少設定：

```env
TWITCH_CHANNEL=你的頻道名
```

啟動 RabbitMQ：

```powershell
docker compose up -d
```

管理介面：http://localhost:15672（帳密 `guest` / `guest`）

### 0.2 通過條件

```powershell
uv run python -m app.main list
```

應能列出已註冊的 publishers 與 subscribers，無 import 或 path 錯誤。

---

## 第 1 層：自動驗證

```powershell
powershell -NoProfile -File scripts/verify_setup.ps1
```

腳本會依序檢查：Python 版本、`uv`、workspace 套件、`.env`、`TWITCH_CHANNEL`、RabbitMQ 連線、單元測試。

### 通過條件

終端最後一行為：

```
SETUP_VERIFICATION_PASS
```

若失敗，依 `[check] FAIL` 後的提示修正，或參考本文 [常見錯誤](#常見錯誤)。

可選進階檢查（跨 process 去重）：

```powershell
uv run python scripts/verify_setup.py --smoke-dedup
```

---

## 第 2 層：手動 smoke（Phase 01，零 OAuth）

此層只驗證「Twitch 聊天 → RabbitMQ → 日誌」，**不需要** Twitch OAuth 或 LLM API key。

開啟**兩個**終端，都在 `streamer_toolbox` 目錄：

```powershell
# 終端 1：訂閱並寫 log
uv run python -m app.main run sub-io-log

# 終端 2：讀取 Twitch 聊天並發布
uv run python -m app.main run ingress-ttv-read
```

請確認 `.env` 的 `TWITCH_CHANNEL` 為**正在直播或有聊天活動**的頻道，否則可能暫時看不到訊息。

### 通過條件

| 項目 | 驗證方式 |
|------|----------|
| 終端機 | 終端 1 印出 `[HH:MM:SS] [msgid] #channel author: content` |
| 檔案 | `logs/chat_io.jsonl` 每行為合法 JSON |
| RabbitMQ | 管理介面可見 exchange `stream_helper`（topic） |

結束時在兩個終端按 **Ctrl+C**。勿直接關閉視窗，以免殘留程序。

---

## 第 3 層：實際跑 LLM Bot

要讓 Bot 在聊天室**發話**並回覆 `!ask`，需額外設定 OAuth、LLM 與知識庫。

### 3.1 最少 `.env` 設定

| 變數 | 說明 |
|------|------|
| `TWITCH_CLIENT_ID` | [Twitch Developer Console](https://dev.twitch.tv/console) 應用程式 ID |
| `TWITCH_CLIENT_SECRET` | 同上 Client Secret |
| `TWITCH_CHANNEL_REFRESH_TOKEN` | 主帳號（頻道擁有者）refresh token |
| `TWITCH_BOT_REFRESH_TOKEN` | Bot 帳號 refresh token |
| `TWITCH_BROADCASTER_ID` | 主帳號使用者 ID |
| `TWITCH_BOT_ID` | Bot 帳號使用者 ID |
| `LLM_BACKEND` | 設為 `gemini` |
| `GOOGLE_AI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) API key |
| `LLM_KNOWLEDGE_BACKEND` | 保持 `chroma` |
| `LLM_KNOWLEDGE_PATH` | 預設 `data/knowledge` |

完整變數說明見 [.env.example](../.env.example)。

### 3.2 OAuth 首次授權（外部工具）

Twitch refresh token **不在本 repo 內產生**。請使用姊妹專案 [`twitch_api`](../twitch_api)（與 `streamer_toolbox` 同層的 `../twitch_api`）：

1. 在 Twitch Developer Console 建立應用，取得 Client ID / Secret，寫入 `.env`
2. 於 `twitch_api` 執行 `scripts/first_time_auth.py` 或 GUI，完成**主帳號**與 **Bot 帳號**授權
3. 將產生的 `TWITCH_*_REFRESH_TOKEN`、`*_ID` 複製回本 repo 的 `.env`

詳細設計見 [architecture/identity-auth.md](architecture/identity-auth.md)、[use-cases/04-oauth.md](use-cases/04-oauth.md)。

### 3.3 知識庫

```powershell
# 複製範本到 data/knowledge/（僅目標不存在時）
powershell -NoProfile -File scripts/setup_knowledge.ps1
```

編輯 `data/knowledge/{TWITCH_CHANNEL}.md`（人設、指令、回覆風格等）。格式說明見 [config/knowledge/README.md](../config/knowledge/README.md)。

驗證 Chroma 是否可讀：

```powershell
uv run python scripts/verify_chroma_knowledge.py
```

### 3.4 啟動 Bot（固定兩終端）

```powershell
# 終端 1：聊天 ingress、STT、直播 metadata、記錄
uv run python -m app.main run --stack ingress

# 終端 2：LLM 問答、長期記憶、twitch 發話
uv run python -m app.main run --stack llm
```

**重要**：`--stack llm` **不含**聊天 ingress。只開終端 2 時，`!ask` 不會觸發。

可選：常駐記憶摘要 worker（需 `GOOGLE_AI_API_KEY`）：

```powershell
uv run python -m app.workers --llm-backend gemini
```

### 3.5 通過條件

| 項目 | 驗證方式 |
|------|----------|
| 聊天觸發 | 在 Twitch 聊天室輸入 `!ask 測試`，Bot 帳號有回覆 |
| 程序數量 | `powershell -File scripts/list_procs.ps1`，關鍵模組各約 1 個 instance |
| 啟動 log | 終端 2 stderr 可見 `llm_client=`、`qa_memory_mode=` 等 |

### 3.6 日常維運

```powershell
# 列出目前在跑的程序
powershell -NoProfile -File scripts/list_procs.ps1

# 停止所有相關程序（重複多開或殘留時）
powershell -NoProfile -File scripts/stop_all.ps1
```

關閉服務請用 **Ctrl+C**，不要直接關終端視窗。

---

## 常見錯誤

| 現象 | 可能原因 | 處理方式 |
|------|----------|----------|
| `path dependency not found` / `ttvchat-lens` 找不到 | clone 不完整或 `uv sync` 未執行 | 確認 `packages/ttvchat-lens` 存在後重新 `uv sync` |
| `ModuleNotFoundError: No module named 'app'` | 未安裝依賴 | 在 repo 根目錄執行 `uv sync`，用 `uv run python -m app.main` |
| `Bind for 0.0.0.0:5672 failed` | 5672 埠被佔用 | 停止其他 RabbitMQ 容器，或共用既有 broker 並確認 `RABBITMQ_URL` |
| `TWITCH_CHANNEL must be set` | `.env` 未設定頻道 | 編輯 `.env` 或 `--channel 頻道名` |
| `!ask` 沒反應 | 只開了 llm stack | 另開終端執行 `--stack ingress` |
| Bot 無法發話 / EventSub 失敗 | OAuth token 過期或 scope 不足 | 重跑 `twitch_api` 授權，更新 `.env` 後 `stop_all.ps1` 再重啟 |
| 中文亂碼 | 終端編碼 | 使用 Windows Terminal；詳見 [development.md](development.md) |

---

## 下一步

| 目標 | 文件 |
|------|------|
| 開發、測試、pre-commit | [development.md](development.md) |
| 模組與產品組合 | [modules.md](modules.md) |
| OAuth 與雙帳號設計 | [architecture/identity-auth.md](architecture/identity-auth.md) |
| 記憶管線（L0–L4） | [architecture/stream-memory-pipeline.md](architecture/stream-memory-pipeline.md) |
