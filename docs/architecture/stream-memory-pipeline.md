# 直播文字記錄與記憶管線

聊天室觸發問答（指令層）與 Web UI **不在本階段範圍**。本文件描述四層架構，並標記目前實作進度。

## 四層架構

| 層 | 路徑 | 職責 | 狀態 |
|----|------|------|------|
| L0 Ingress | `app/publishers/` | 讀平台 → publish MQ | 已有 |
| L1 記錄 | `app/subscribers/stream_record.py` | `chat.message` / `stt.segment` → SQLite | **Phase 2** |
| L2 記憶 | `app/workers/` | 定期摘要 → `summaries` 表 | **Phase 2** |
| L3 指令 | （規劃） | `!ask` → 查 DB/RAG → LLM → `chat.reply` | 未實作 |
| L4 LLM | （規劃） | 無狀態推理 | 未實作 |

共用持久化：`pkg-stream-store`（SQLite schema + CRUD）。

## Phase 2 資料流（聊天 + STT）

```mermaid
flowchart LR
    IRC["ingress-ttv-read"] -->|chat.message| MQ[("RabbitMQ")]
    Audio["ingress-twitch-audio"] -->|stt.segment| MQ
    MQ --> Rec["app.subscribers.stream_record"]
    Rec --> DB[("pkg-stream-store<br/>SQLite")]
    Worker["app.workers<br/>定時"] --> DB
    Worker --> Sum[("summaries 表")]
```

## `RECORD_MODE`

| 值 | 說明 |
|----|------|
| `chat` | 只記 `chat.message` |
| `stt` | 只記 `stt.segment` |
| `both` | 聊天室 + 實況語音 STT；記憶層**合併**時序摘要並標註問答對照 |

## SQLite 表

- `stream_sessions` — 場次
- `text_records` — 原始文字（`source=chat` 或 `stt`）
- `summaries` — 記憶層產出的摘要（`source=chat` / `stt` / `both`；`both` 為合併問答摘要）
- `memory_checkpoints` — worker 游標

## 環境變數

| 變數 | 預設 | 說明 |
|------|------|------|
| `RECORD_MODE` | `chat` | `chat` / `stt` / `both` |
| `STREAM_DB_PATH` | `data/stream_text.db` | SQLite 路徑 |
| `STREAM_SESSION_ID` | （自動） | 可选手動指定場次 ID |
| `MEMORY_INTERVAL_MINUTES` | `5` | 摘要週期 |
| `MEMORY_LLM_BACKEND` | `template` | `template` 或 `openai`/`gemini` |
| `STT_*` | 見 `.env.example` | `ingress-twitch-audio` 用 |

## 啟動（RECORD_MODE=both）

```powershell
docker compose up -d
uv run python -m app.main run ingress-ttv-read ingress-twitch-audio sub-stream-record
# 另開終端
uv run python -m app.workers --llm-backend gemini
```

`.env` 需設定 `RECORD_MODE=both` 與 `TWITCH_CHANNEL`（STT 與 IRC 共用頻道）。

指令層待 OAuth 就緒後再接。
