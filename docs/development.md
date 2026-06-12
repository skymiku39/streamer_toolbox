# 開發環境設定

本 repo 為**唯一正式實作根目錄**：設計文件在 `docs/`，程式在 workspace package 與 `app/`。姊妹專案 [streamer-toolkit](references/streamer-toolkit.md) 僅供架構參考。

契約以 [events.md](events.md) 為準。

## 前置需求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker Desktop（RabbitMQ 本地開發用）

## 初次設定

```powershell
cd streamer_toolbox
uv sync
copy .env.example .env
```

編輯 `.env`：至少設定 `TWITCH_CHANNEL`（要收聽的 Twitch 頻道，不含 `#`）。

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

```
streamer_toolbox/
├── app/
│   ├── main.py              # CLI 編排
│   ├── publishers/          # Ingress（ingress_*）
│   ├── subscribers/         # Sub（sub_*、twitch_connector）
│   └── workers/             # 定時 worker（記憶層等）
├── config/                  # 各 Sub 設定 JSON
├── docs/
├── pkg-events/              # 事件 schema
├── pkg-bus/                 # RabbitMQ helpers
├── pkg-stream-store/        # SQLite 記錄/記憶
├── identity-oauth/
├── docker-compose.yml
└── pyproject.toml
```

## 設計約束

實作須遵守 [solid.md](solid.md) 與 [events.md](events.md)。契約變更先改文件，再改 `pkg-events`。

## 常見問題

### `ModuleNotFoundError: No module named 'app'`

請先 `uv sync`，並在 repo 根目錄執行 `uv run python -m app.main`。

### `Bind for 0.0.0.0:5672 failed`

5672 已被佔用。可共用現有 RabbitMQ，或 `docker stop <容器名>` 後再 `docker compose up -d`。

### `TWITCH_CHANNEL must be set`

在 `.env` 設定 `TWITCH_CHANNEL`，或 `uv run python -m app.publishers.ingress_ttv_read --channel 頻道名`。
