# 開發環境設定

若你**只想跑 Bot、較少改程式**，請先看 [getting-started.md](getting-started.md)（安裝布局、`verify_setup`、雙 stack 啟動）。

本 repo 為**唯一正式實作根目錄**：設計文件在 `docs/`，程式在 workspace package 與 `app/`。姊妹專案 [streamer-toolkit](references/streamer-toolkit.md) 僅供架構參考。

契約以 [events.md](events.md) 為準。

## 前置需求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker Desktop（RabbitMQ 本地開發用）

### Windows 終端機中文亂碼

`app.main` 會將主控台設為 **UTF-8**（含 Windows `SetConsoleOutputCP(65001)`），runner 亦以 UTF-8 讀寫子程序輸出。若仍見亂碼：

1. 使用 **Windows Terminal** 或 VS Code / Cursor 內建終端（比舊版 `cmd` 相容性佳）
2. 可選：啟動前執行 `chcp 65001`（切換 code page 為 UTF-8）
3. 可選：PowerShell profile 加入 `[Console]::OutputEncoding = [System.Text.UTF8Encoding]::UTF8`

直接跑單一模組時同樣建議透過 `uv run python -m app.main run ...`，以套用 runner 的 UTF-8 子程序設定。

## 初次設定

```powershell
cd streamer_toolbox
uv sync
copy .env.example .env
```

編輯 `.env`：至少設定 `TWITCH_CHANNEL`（要收聽的 Twitch 頻道，不含 `#`）。

設定分三層（`.env` / `STREAMER_CONFIG_DIR` / repo `config/`），完整說明見 [configuration.md](configuration.md)。

## RabbitMQ

```powershell
docker compose up -d
```

管理介面：http://localhost:15672（guest / guest）

若 5672 已被其他專案佔用，可共用同一 broker（`RABBITMQ_URL` 指向 `127.0.0.1:5672`），或先停止舊容器再啟動本 repo 的 compose。

## 執行測試

```powershell
uv run pytest
uv run ruff check .
```

## Pre-commit（秘密、執行期資料與 commit 格式）

初次設定後，每次 `git commit` 會自動執行：

- gitleaks 與 runtime 檔案阻擋（`.env`、`data/`、`*.db` 等）
- **commit 訊息格式**（僅允許 `type: emoji [AI] subject`）

```powershell
uv sync
uv run pre-commit install
uv run pre-commit run --all-files
```

commit 訊息範例：`feat: ✨ [AI] 新增 ingress-twitch-stream 並餵入 sub-llm 直播 metadata`

## 憑證輪替（隱私事件後建議）

歷史掃描未發現 API key 進版控，但若曾擔心本機 `.env` 外洩，請手動輪替：

| 變數 | 輪替方式 |
|------|----------|
| `TWITCH_CLIENT_SECRET` | [Twitch Developer Console](https://dev.twitch.tv/console) 重設 Client Secret |
| `TWITCH_*_REFRESH_TOKEN` | 重新走 OAuth 授權，更新 `.env` |
| `GOOGLE_AI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) 撤銷並建立新 key |
| `DISCORD_BOT_TOKEN` | Discord Developer Portal 重設 Bot Token |

輪替後刪除本機 `.tio.tokens.json`，重啟相關 process 讓新憑證生效。

## Phase 01 端對端實測

### 列出 process

```powershell
uv run python -m app.main list
```

### 全棧（Pub + Sub）

```powershell
docker compose up -d
uv run python -m app.main run
```

### 分開終端機（驗證解耦）

```powershell
# 終端 1
uv run python -m app.main run sub-io-log

# 終端 2
uv run python -m app.main run ingress-ttv-read
```

也可直接呼叫各模組：

```powershell
uv run python -m app.publishers.ingress_ttv_read --channel your_channel
uv run python -m app.subscribers.sub_io_log
uv run python -m app.workers --once --llm-backend gemini
```

### 產品 C：sub-llm 問答

```powershell
# 終端 1：聊天 ingress + LLM sub + connector（依 modules 啟用表調整）
uv run python -m app.main run sub-llm twitch-connector ingress-ttv-read

# 或直接跑 sub-llm（需 RabbitMQ 與其他 ingress 已發布 chat.message / stt.segment）
uv run python -m app.subscribers.sub_llm --llm-backend template
```

`.env` 常用設定（完整清單見 `.env.example`）：

| 變數 | 說明 |
|------|------|
| `LLM_TRIGGER_PREFIXES` | 觸發前綴（預設 `!ask`） |
| `LLM_BACKEND` | `template` / `openai` / `gemini` |
| `LLM_MAX_REPLY_LENGTH` | 回覆正文上限（預設 200；不含 @/# tag 與標點；設 0 則不截正文，僅受 Twitch 500 字限制） |
| `QA_MEMORY_MODE` | Bot 問答長期記憶：`none`（預設，不讀寫 qa）／`structured`／`batch`（2、3 讀取相同） |
| `LLM_QA_MEMORY_MIN_VALUE` | `structured` 模式最低 memory_value（預設 3） |
| `LLM_SYSTEM_PROMPT` | 系統提示；預設要求勿用 Markdown，以純文字短句回覆 |
| `LLM_CONTEXT_WINDOW_MINUTES` | STT / 聊天短期上下文（分鐘，預設 **15**） |
| `LLM_BOT_REPLY_WINDOW_MINUTES` | Bot 近期問答 buffer 時間窗（預設 30；**不寫入 RAG**） |
| `LLM_BOT_REPLY_MAX_PAIRS` | Bot 近期問答保留則數（預設 5） |
| `LLM_MEMORY_FROM_DB` | 是否啟用 L2 摘要 Chroma RAG（`kb_memory`，預設 `true`） |
| `LLM_MEMORY_SUMMARY_LIMIT` | 同步至 Chroma 的摘要筆數上限 |
| `LLM_STARTUP_ANNOUNCEMENT` | 程序啟動是否發 LLM 問候至聊天室（預設 `true`） |
| `LLM_GAME_INFO_ENABLED` | 直播中是否注入 IGDB 遊戲資料（預設 `true`） |
| `LLM_GAME_INFO_CACHE_TTL_SECONDS` | IGDB 查詢快取秒數（預設 3600） |
| `LLM_KNOWLEDGE_PATH` | 知識庫檔案或目錄（可選） |
| `LLM_KNOWLEDGE_BACKEND` | 知識庫後端，**僅支援 `chroma`**（Chroma 向量 RAG；`file` 關鍵字後端已停用） |
| `LLM_CHROMA_DIR` | Chroma 持久化目錄（靜態知識 + L2 摘要向量索引） |
| `LLM_CHROMA_QUERY_LIMIT` | 靜態知識庫 RAG 回傳片段數（預設 3） |
| `LLM_CHROMA_MEMORY_QUERY_LIMIT` | L2 摘要 RAG 回傳片段數（預設 5） |

首次啟用 Chroma 時，先將 `config/knowledge/{TWITCH_CHANNEL}.md` 複製到 `data/knowledge/`：

```powershell
powershell -NoProfile -File scripts/setup_knowledge.ps1
uv run python scripts/verify_chroma_knowledge.py
```

LLM 回覆在 `safety.filter_output` 之後會經 `plain_text_for_chat` 去除 Markdown，再截斷長度並發布 `chat.reply`。

**避免連發：** 同一頻道只跑一組 ingress / sub-llm / twitch-connector。系統以兩層防護：

1. **PID 單例鎖**（`data/process-locks/{name}.pid`）：每個 publisher/subscriber/worker 啟動時若同名 process 已在跑，會立即退出並提示；`app.main run` 也會在 spawn 前檢查。
2. **SQLite 冪等去重**（`IdempotencyStore`，預設共用 `STREAM_DB_PATH`）：同一 `message_id` 只 publish / 觸發 LLM / 送 Twitch 一次。

**維運腳本（Windows PowerShell）：**

```powershell
# 列出目前 streamer 相關 Python 程序（關鍵模組應各 1 個）
powershell -NoProfile -File scripts/list_procs.ps1

# 清掉殘留程序（重複多開、直接關終端未 Ctrl+C 時）
powershell -NoProfile -File scripts/stop_all.ps1
```

關閉服務請用 **Ctrl+C**，不要直接關終端視窗。建議固定兩個終端：

```powershell
# 終端 1（ingress 含 stream.metadata）
uv run python -m app.main run --stack ingress

# 終端 2（LLM + connector）
uv run python -m app.main run --stack llm
```

跨 process 去重自測（Windows 請用腳本，勿用 `multiprocessing.Pool` 搭配 `python -c`）：

```powershell
uv run python scripts/verify_dedup.py
```

成功時輸出 `VERIFICATION_PASS wins_per_layer=1`。

### 記錄層 + 記憶層（Phase 1）

```powershell
uv run python -m app.main run ingress-ttv-read sub-stream-record
uv run python -m app.workers --once --llm-backend gemini
```

### 預期結果

| 項目 | 驗證方式 |
|------|----------|
| Exchange | RabbitMQ UI 可見 `stream_helper`（topic） |
| Queue | `sub.io_log.chat_message` 綁定 `chat.message` |
| 終端機 | Sub 印出 `[HH:MM:SS] [msgid] #channel author: content` |
| 檔案 | `logs/chat_io.jsonl` 每行為合法 `events.md` JSON |

## Workspace 結構

根目錄 `pyproject.toml` 以 uv workspace 管理 monorepo：

```toml
[tool.uv.workspace]
members = [
    "app",
    "packages/*",
]
```

```
streamer_toolbox/
├── pyproject.toml           # Workspace 定義
├── app/
│   ├── pyproject.toml       # streamer-app 依賴
│   ├── src/app/             # 主程式、processes、publishers、subscribers、workers、memory_view
│   └── tests/
├── packages/
│   ├── bus/
│   ├── events/
│   ├── game-info/
│   ├── identity-oauth/
│   ├── safety/
│   ├── stream-store/
│   ├── tts/
│   ├── ttvchat-lens/        # Twitch IRC 匿名唯讀
│   └── tubechat-lens/       # YouTube 直播聊天唯讀
├── config/
├── docs/
├── docker-compose.yml
└── ...
```

## 命名慣例

模組命名刻意在兩種風格間切換，新增 process 時請對齊：

| 對象 | 風格 | 範例 |
|------|------|------|
| Process 名（CLI、`app.main list`、PID 鎖） | kebab-case | `ingress-twitch-audio`、`sub-character-brain` |
| Python 套件目錄／import | snake_case | `ingress_twitch_audio`、`sub_character_brain` |

其他約定：

- **`sub_` 前綴**：消費事件並產生業務結果的 subscriber 才加 `sub_`。`twitch_connector` 是
  egress 連接器（將 `chat.reply` 送回 Twitch），非業務 sub，因此**不加** `sub_` 前綴。
- **Legacy 扁平模組**：多數 subscriber 已收斂為 `sub_<name>/` 子目錄；`sub-stream-record`
  仍為扁平三檔（`stream_record.py`、`stream_record_config.py`、`stream_record_writer.py`），
  屬已知歷史例外，待後續再目錄化，process 名 `sub-stream-record` 不變。

## 設計約束

實作須遵守 [solid.md](solid.md) 與 [events.md](events.md)。契約變更先改文件，再改 `packages/events`。

## 常見問題

### `ModuleNotFoundError: No module named 'app'`

請先 `uv sync`，並在 repo 根目錄執行 `uv run python -m app.main`。

### `Bind for 0.0.0.0:5672 failed`

5672 已被佔用。可共用現有 RabbitMQ，或 `docker stop <容器名>` 後再 `docker compose up -d`。

### `TWITCH_CHANNEL must be set`

在 `.env` 設定 `TWITCH_CHANNEL`，或 `uv run python -m app.publishers.ingress_ttv_read --channel 頻道名`。
