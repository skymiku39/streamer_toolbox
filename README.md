# streamer-toolbox

直播互動助手的**設計文件庫與 stream-core 實作根目錄**。以 Pub/Sub、可組裝模組與 **[SOLID](docs/solid.md)** 為強制約束。

| 區塊 | 路徑 | 說明 |
|------|------|------|
| 設計文件 | `docs/` | 契約、模組、部署、使用案例 |
| 應用層 | `app/` | Pub/Sub 程序編排（`streamer-app`） |
| 共用套件 | `packages/` | `bus`、`events`、`safety`、`stt-core`、`stream-store`、`tts`、`identity-oauth`、`game-info`、`control`、`emotes`、`streamer-config`、`ttvchat-lens`、`tubechat-lens`、`voice-clone` |
| 開發工具 | `tools/` | `streamer-config-gui`（設定編輯 GUI） |

## 使用者分流

| 你是… | 從這裡開始 |
|--------|------------|
| **不確定要開哪種模式** | [docs/operator-modes.md](docs/operator-modes.md) |
| **想跑直播 Bot**（安裝、驗證、啟動） | [docs/getting-started.md](docs/getting-started.md) |
| **想開發／改程式** | [docs/development.md](docs/development.md) |

## 快速開始（開發）

```powershell
uv sync
copy .env.example .env
docker compose up -d
powershell -NoProfile -File scripts/verify_setup.ps1
uv run python -m app.main run
```

驗證腳本通過後應輸出 `SETUP_VERIFICATION_PASS`。詳見 [docs/development.md](docs/development.md)。架構參考見姊妹專案 [`../streamer-toolkit`](../streamer-toolkit)（非正式執行環境）。

## 姊妹專案

| 專案 | 路徑 | 角色 |
|------|------|------|
| streamer-toolkit | [`../streamer-toolkit`](../streamer-toolkit) | Phase 01 MQ Pub/Sub 可執行參考 |

## 參考程式碼

下列為**歷史 As-is** 實作，供對照邏輯；**執行期不依賴**，僅需 clone 本 repo：

| 專案 | 角色 |
|------|------|
| [`../twitch_api`](../twitch_api) | 產品 B 歷史參考（OAuth、EventSub、規則 BOT） |
| [`../llm_twitchat`](../llm_twitchat) | 產品 C 歷史參考（STT + Gemini Web App） |

聊天讀取已收編：`packages/ttvchat-lens`、`packages/tubechat-lens`。

詳見 [docs/references.md](docs/references.md)。

## 文件索引

### 核心規範

| 文件 | 內容 |
|------|------|
| [docs/overview.md](docs/overview.md) | 總覽、文件地圖、決策流程 |
| [docs/solid.md](docs/solid.md) | **SOLID 強制準則**、檢查清單 |
| [docs/events.md](docs/events.md) | Topic 與 payload 契約 |
| [docs/modules.md](docs/modules.md) | 模組目錄、產品 A～D、App 啟用表 |
| [docs/packages.md](docs/packages.md) | repo/package 規劃與依賴規則 |
| [docs/deployment.md](docs/deployment.md) | Pub/Sub 部署、MQ、可觀測性 |
| [docs/references.md](docs/references.md) | 姊妹專案、參考程式碼、Sub/Ingress 對照、twitch_api 遷移 |
| [docs/references/streamer-toolkit.md](docs/references/streamer-toolkit.md) | Phase 01 參考實作（streamer-toolkit） |
| [docs/references/llm-twitchat.md](docs/references/llm-twitchat.md) | 產品 C As-is（llm_twitchat） |
| [docs/getting-started.md](docs/getting-started.md) | **營運者**：安裝、驗證、啟動 Bot |
| [docs/operator-modes.md](docs/operator-modes.md) | **營運者**：運作模式 0～5、與舊專案對照 |
| [docs/development.md](docs/development.md) | 開發環境、測試、workspace 結構 |
| [docs/checklists/pub-sub-writing.md](docs/checklists/pub-sub-writing.md) | Pub/Sub 各 package 撰寫清單 |

### 使用案例（時序圖）

| 文件 | 產品 |
|------|------|
| [01-show.md](docs/use-cases/01-show.md) | A：純聊天 overlay |
| [02-rule-bot.md](docs/use-cases/02-rule-bot.md) | B：規則 BOT |
| [03-llm-bot.md](docs/use-cases/03-llm-bot.md) | C：LLM BOT |
| [04-oauth.md](docs/use-cases/04-oauth.md) | OAuth 橫切 |
| [05-character.md](docs/use-cases/05-character.md) | D：虛擬角色 |

## 建議閱讀順序

1. [overview.md](docs/overview.md)
2. [solid.md](docs/solid.md)
3. [modules.md](docs/modules.md) + [events.md](docs/events.md)
4. [02-rule-bot.md](docs/use-cases/02-rule-bot.md)
5. [deployment.md](docs/deployment.md) + [packages.md](docs/packages.md)

## 實作計畫

| 階段 | 文件 | 說明 |
|------|------|------|
| **Phase 01** | [phase-01-rabbitmq-io-poc.md](docs/plans/phase-01-rabbitmq-io-poc.md) | RabbitMQ：Twitch Pub → I/O Log Sub |

## 產品速查

| 產品 | 一句話 |
|------|--------|
| **A** | ingress → MQ → overlay |
| **B** | + bot-logic → chat.reply → connector |
| **C** | + sub-llm + 雙閘門 safety |
| **D** | + character.turn 管線（TTS+表情+OBS 同步） |

圖表使用 [Mermaid](https://mermaid.js.org/)，可貼至 [mermaid.live](https://mermaid.live) 預覽。
