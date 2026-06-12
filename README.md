# stream_helper

直播互動助手的**完整設計文件庫**。以 Pub/Sub、可組裝模組與 **[SOLID](docs/solid.md)** 為強制約束，指導現有與未來所有 repo/package。本 repo **不含可執行程式**。

## 姊妹專案

| 專案 | 路徑 |
|------|------|
| twitch-oauth-bot | [`../twitch_api`](../twitch_api) |
| TubeChat Lens | [`../yt_chat`](../yt_chat) |
| ttvchat-lens | [`../ttv_chat`](../ttv_chat) |

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
| [docs/references.md](docs/references.md) | 姊妹專案、twitch_api 遷移 |

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
