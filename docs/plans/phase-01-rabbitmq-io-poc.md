# Phase 01：RabbitMQ 1 Pub + 1 Sub（Twitch 聊天 → I/O Log）

| 項目 | 內容 |
|------|------|
| 狀態 | **本專案已實作**（見 [development.md](../development.md)；姊妹專案 [streamer-toolkit](../references/streamer-toolkit.md) 為早期架構參考） |
| 目標 | 驗證 **外部 RabbitMQ** 可承載 `chat.message`，打通最小 Pub/Sub 管線 |
| 對應產品 | 產品 A 的子集（僅 ingress + I/O 檢查，尚無 overlay） |
| 依據文件 | [events.md](../events.md)、[solid.md](../solid.md)、[packages.md](../packages.md) |

## 0. 實作狀態

**本專案**（`streamer_toolbox`）已實作對齊設計的 Phase 01 管線，執行方式見 [development.md](../development.md)。

姊妹專案 [`streamer-toolkit`](../../streamer-toolkit) 為早期可執行範本（fanout 拓撲、精簡 schema），僅供架構對照。詳見 [references/streamer-toolkit.md](../references/streamer-toolkit.md)。

| 面向 | 計畫目標 | 本專案現況 | toolkit（參考） |
|------|----------|------------|-----------------|
| Pub / Sub 解耦 | 獨立 process | 已達成 | 已達成（`pub1`、`sub1`、`sub2`） |
| RabbitMQ fan-out | 多 Sub 訂閱同一來源 | 已達成（topic） | 已達成（fanout `twitch.chat`） |
| Twitch IRC 匿名讀取 | 零 OAuth | 已達成 | 已達成（內建 `twitch_irc.py`） |
| Exchange / routing | topic `stream_helper` / `chat.message` | **已對齊** | 未對齊（fanout `twitch.chat`） |
| JSON schema | 完整 `events.md#chatmessage` | **已對齊** | 未對齊（精簡 4 欄位） |
| I/O log 格式 | JSONL | **已對齊** | 未對齊（`sub1` 文字行） |
| `pkg-events` / `pkg-bus` | 獨立 package | **已拆** | 未拆（合併於 `app/messaging/`） |

## 1. 要做什麼

```mermaid
flowchart LR
    Twitch[Twitch_IRC]
    Pub[ingress_twitch_chat]
    RMQ[(RabbitMQ)]
    Sub[sub_io_log]
    Out[終端機與_LOG_檔]

    Twitch --> Pub
    Pub -->|publish chat.message| RMQ
    RMQ -->|subscribe| Sub
    Sub --> Out
```

| 元件 | 職責 | 一句話 |
|------|------|--------|
| **Pub** | `ingress-twitch-chat` | 連 Twitch 聊天室，normalize 後 publish JSON |
| **Sub** | `sub-io-log` | 訂閱 `chat.message`，**顯示並寫 LOG**，專門驗證 I/O |
| **MQ** | RabbitMQ | 解耦 Pub / Sub，可各開一個終端機 process |
| **App** | 本階段可省略 | 手動各啟一個 process；或簡易 `docker compose up` |

**不做：** LLM、發話、OAuth、overlay、Dashboard、EventSub 非聊天事件。

## 2. 為何 Pub 選 Twitch IRC（`ttv_chat`）

| 方案 | 優點 | 本階段 |
|------|------|--------|
| `ttv_chat`（IRC 匿名） | 零 OAuth、已有 `ChatMessage`、適合本地 POC | **採用** |
| `twitch_api` EventSub | 與產品 B 一致 | Phase 02+ |
| `yt_chat` | 可換平台測 | 非本階段重點 |

Pub **只負責**讀取 + normalize + publish，不寫 log 檔（log 是 Sub 的事）——符合 SOLID **S**。

## 3. RabbitMQ 拓撲

### 3.1 命名

| 項目 | 值 |
|------|-----|
| Exchange | `stream_helper`（type: **topic**, durable） |
| Routing key | `chat.message` |
| Queue（Sub 專用） | `sub.io_log.chat_message` |
| Binding | `stream_helper` ──`chat.message`──► `sub.io_log.chat_message` |

### 3.2 訊息格式

Body 為 [events.md `chat.message`](../events.md#chatmessage) JSON，`platform` 固定 `"twitch"`。

```json
{
  "schema_version": 1,
  "topic": "chat.message",
  "platform": "twitch",
  "message_id": "...",
  "author_name": "viewer",
  "login": "viewer_login",
  "content": "hello",
  "timestamp": "2026-06-12T17:00:00+08:00",
  "channel": "some_channel"
}
```

### 3.3 連線環境變數（共用）

```env
RABBITMQ_URL=amqp://guest:guest@127.0.0.1:5672/
STREAM_EXCHANGE=stream_helper
```

Pub 額外：

```env
TWITCH_CHANNEL=your_channel
```

Sub 額外：

```env
IO_LOG_PATH=logs/chat_io.jsonl
IO_LOG_CONSOLE=true
```

## 4. 程式 / Repo 規劃

### 4.0 放哪個 repo？

| Package | Phase 01 位置 | 長期歸屬 |
|---------|---------------|----------|
| `pkg-events`, `pkg-bus` | 本專案 | **本專案 `streamer_toolbox`**（永久） |
| `sub-io-log` | 本專案 | **本專案**（簡單、維運必用，不拆） |
| `ingress-twitch-chat` | 本專案內目錄 | 介面穩定後可拆成獨立 `ingress-ttv-read` repo |

原則見 [packages.md#本專案-vs-獨立-repo](../packages.md#本專案-vs-獨立-repo)：

- **介面未穩定前**：全部在本專案目錄內開發，不急着拆 Git remote。
- **`sub-io-log`**：屬診斷/基礎設施，**即使介面穩定也留在本專案**。
- **複雜或可選 Sub**（bot、llm、overlay、character）：`events.md` + `pkg-bus` 凍結後再拆獨立 repo。

### 4.1 目錄（Phase 01 孵化）

```
streamer_toolbox/                  # 本專案
├── docs/                          # 設計文件
├── docker-compose.yml             # RabbitMQ
├── pyproject.toml                 # uv workspace
├── pkg-events/
├── pkg-bus/
├── ingress-twitch-chat/           # Pub（日後可拆）
└── sub-io-log/                    # Sub，永久留本專案
```

### 4.2 `pkg-events`

- `ChatMessageEvent` dataclass / pydantic model
- `TOPIC_CHAT_MESSAGE = "chat.message"`
- `to_json()` / `from_json()`，對齊 [events.md](../events.md)
- **無** RabbitMQ、無 Twitch 依賴

### 4.3 `pkg-bus`

```python
class EventBus(Protocol):
    def publish(self, topic: str, payload: dict) -> None: ...
    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> None: ...
```

- `RabbitMQBus`：連線、declare exchange、publish、consume
- 本階段可不實作 `InProcessBus`（Phase 02 再補對照測試）

### 4.4 `ingress-twitch-chat`（Pub）

| 項目 | 說明 |
|------|------|
| 依賴 | `ttvchat-lens`（workspace `packages/ttvchat-lens`）或複製 reader 介面 |
| 流程 | `LiveChatReader` → `on_message` → map 成 `ChatMessageEvent` → `bus.publish("chat.message", ...)` |
| 入口 | `uv run ingress-twitch-chat` |
| 禁止 | 訂閱 queue、寫業務 log 檔、呼叫 Sub |

**Mapping（`ttv_chat.ChatMessage` → event）：**

| ChatMessage | Event 欄位 |
|-------------|------------|
| `message_id` | `message_id` |
| `author_name` | `author_name` |
| `author_id` | 放入 `raw` 或擴充欄位 |
| `message` | `content` |
| `timestamp` | ISO 8601 |
| 頻道參數 | `channel` |
| — | `platform: "twitch"` |

### 4.5 `sub-io-log`（Sub，常駐本專案）

專門檢查 **I/O 是否正確收到 Pub 內容** 的診斷用 Sub。

| 項目 | 說明 |
|------|------|
| 訂閱 | `chat.message` |
| 終端機 | 每則訊息一行：`[HH:MM:SS] #channel author: content`（`rich` 可選） |
| 檔案 | 追加 JSON Lines 至 `IO_LOG_PATH` |
| 統計 | 每 30s 印 received count、最後一則 timestamp（確認沒斷流） |
| 入口 | `uv run sub-io-log` |
| 禁止 | 連 Twitch、publish 訊息、修改 payload |

可選：收到時印 `message_id` 前 8 碼，方便對照 Pub 端 debug。

## 5. 實作步驟

### Step 0：環境

- [ ] 安裝 Docker Desktop（或本機 RabbitMQ）
- [ ] `docker-compose.yml` 啟動 RabbitMQ（port 5672、15672 管理介面）
- [ ] 確認 `http://localhost:15672` 可登入（guest/guest）

### Step 1：`pkg-events`

- [ ] 定義 `ChatMessageEvent` + JSON 序列化
- [ ] 單元測試：round-trip JSON、必填欄位驗證

### Step 2：`pkg-bus`（RabbitMQ）

- [ ] `RabbitMQBus.publish(topic, dict)`
- [ ] `RabbitMQBus.subscribe(topic, handler)`（blocking consume 或 asyncio，擇一）
- [ ] 啟動時 declare exchange + queue + bind
- [ ] 單元測試（可選）：mock 或 testcontainers；至少手動整合測

### Step 3：`ingress-twitch-chat`

- [ ] 整合 `ttvchat_lens.LiveChatReader`
- [ ] 每則聊天 `publish("chat.message", ...)`
- [ ] CLI：`--channel` 或 `TWITCH_CHANNEL`
- [ ] 優雅關閉（Ctrl+C 斷開 IRC + MQ）

### Step 4：`sub-io-log`

- [ ] subscribe `chat.message`
- [ ] console + jsonl 雙寫
- [ ] 週期統計 log

### Step 5：端對端驗收

見下方「驗收標準」。

### Step 6：文件回寫

- [x] 本計畫狀態改為「本專案已實作」
- [x] [deployment.md](../deployment.md) 補充 Phase 01 實作說明
- [x] [packages.md](../packages.md) 標註目錄結構
- [x] 新增 [references/streamer-toolkit.md](../references/streamer-toolkit.md) 專章（姊妹專案架構參考）

## 6. 驗收標準

| # | 條件 | 本專案狀態 |
|---|------|------------|
| 1 | RabbitMQ 管理介面可見 exchange `stream_helper`、queue `sub.io_log.chat_message` | 已達成 |
| 2 | 開 Pub 連線**正在直播**的 Twitch 頻道 | 已達成 |
| 3 | Sub 終端機**即時**印出觀眾聊天內容 | 已達成 |
| 4 | `logs/chat_io.jsonl` 每行為合法 JSON，欄位符合 `events.md` | 已達成 |
| 5 | Pub / Sub **各獨立 process**；重啟 Sub 不影響 Pub 繼續 publish | 已達成 |
| 6 | 重啟 Sub 後（queue durable）可繼續收到**新**訊息（不要求歷史重播，除非刻意設 persistent） | 已達成 |

## 7. 手動驗收流程

**本專案**（正式驗收路徑）：

```powershell
cd streamer_toolbox
docker compose up -d
uv sync
# 設定 .env 中的 TWITCH_CHANNEL
uv run python -m app.main run
```

或分開終端機：

```powershell
uv run python -m app.main run sub-io-log
uv run python -m app.main run ingress-twitch-chat
```

預期：Sub 終端機即時印出聊天；`logs/chat_io.jsonl` 為合法 JSONL。

**姊妹專案 streamer-toolkit**（架構對照，非正式驗收）：

```powershell
cd ../streamer-toolkit
docker compose up -d
uv run python -m app.main run
```

預期：`sub1` 寫入 `logs/chat.log`；`sub2` 於 http://127.0.0.1:8080 顯示即時聊天（schema / 拓撲與設計文件不同）。

## 8. SOLID 自檢（本階段）

| 原則 | 本階段做法 |
|------|------------|
| **S** | Pub 只發、Sub 只收+log；MQ 設定獨立在 `pkg-bus` |
| **O** | 加 SHOW overlay = 新 Sub 綁同一 routing key，不改 Pub |
| **L** | `EventBus` Protocol；日後可換 Redis 實作 |
| **I** | Sub 只依賴 `subscribe` + handler，不依賴 Pub 程式 |
| **D** | 兩者只依賴 `pkg-events` JSON，不依賴 `ttvchat_lens` 類型 |

## 9. 技術選型

| 項目 | 選擇 |
|------|------|
| Python | >= 3.11 |
| 套件管理 | uv workspace |
| RabbitMQ 客戶端 | `pika`（同步，簡單）或 `aio-pika`（若 Pub 已 asyncio） |
| Twitch 讀取 | 參考程式碼 `ttv_chat`（`ttvchat_lens`） |
| Log | stdlib `logging` + JSONL 檔 |

## 10. 風險與對策

| 風險 | 對策 |
|------|------|
| 頻道未開播 | 文件註明需 live channel；Pub 印連線狀態 |
| IRC 斷線 | Pub 自動重連（`ttv_chat` 已有）；重連後繼續 publish |
| JSON 過大 | 本階段不附 `raw` 巨大物件 |
| Windows 路徑 | `IO_LOG_PATH` 用相對路徑 `logs/` |

## 11. 何時從本專案拆出獨立 repo

| 里程碑 | 動作 |
|--------|------|
| Phase 01 完成 | `pkg-events`、`pkg-bus`、`sub-io-log` **留在本專案** |
| `events.md` schema v1 凍結 | 允許新 Sub 以 git 依賴 `pkg-events` 在獨立 repo 開發 |
| Phase 02+ 加 `sub-show-overlay` | 新建獨立 repo，只依賴 pkg，經 MQ 連通 |
| Ingress 多實作並存 | `ingress-twitch-eventsub` 等拆出，本專案只留最小 IRC ingress 或全拆 |

**`sub-io-log` 不拆**——作為管線健康檢查工具，與 `stream-app` 一同維護。

## 12. 後續 Phase（預覽）

| Phase | 內容 |
|-------|------|
| **02** | 加 `sub-show-overlay`（第二個 Sub，驗證 fan-out） |
| **03** | Pub 改 `twitch_api` EventSub + OAuth |
| **04** | `stream-app` 讀 YAML 啟停 Pub/Sub |
| **05** | `sub-bot-logic` + `twitch-connector` |

## 13. 相關文件

- [references/streamer-toolkit.md](../references/streamer-toolkit.md) — 參考實作對照與演進路徑
- [modules.md#產品-a](../modules.md) — 模組對應
- [use-cases/01-show.md](../use-cases/01-show.md) — 完整產品 A 時序
- [deployment.md](../deployment.md) — MQ 選型
