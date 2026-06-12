# 參考專案與遷移

## 姊妹專案

| 專案 | 路徑 | 用途 | 目標 package |
|------|------|------|----------------|
| streamer-toolkit | [`../streamer-toolkit`](../streamer-toolkit) | Phase 01 參考實作（RabbitMQ Pub/Sub POC） | 孵化 `pkg-events`、`pkg-bus`、`ingress-*`、`sub-io-log` |
| twitch-oauth-bot | [`../twitch_api`](../twitch_api) | 全功能 Twitch BOT | 多數 `sub-*` / `ingress-twitch-eventsub` |
| TubeChat Lens | [`../yt_chat`](../yt_chat) | YT 唯讀 | `ingress-yt-read` |
| ttvchat-lens | [`../ttv_chat`](../ttv_chat) | Twitch IRC 唯讀 | `ingress-ttv-read` |

### streamer-toolkit

Phase 01 可執行範本：Twitch IRC（匿名）→ RabbitMQ fanout → 多 Sub（檔案 log、web UI）。與 `ttv_chat` 同為 IRC 匿名讀取，但 toolkit 為自包含實作，示範完整 Pub/Sub 管線與 process registry 擴充模式。

詳見 [references/streamer-toolkit.md](references/streamer-toolkit.md)。

### yt_chat / ttv_chat

- `ChatMessage` + `to_dict()` → 對齊 [events.md#chatmessage](events.md#chatmessage)
- WebSocket：`8765` / `8766`
- 設計筆記：用 Queue 消費，避免 handler 內 I/O

### twitch_api vs ttv_chat

| | ttv_chat | twitch_api |
|---|----------|------------|
| 連線 | IRC 匿名 | EventSub + OAuth |
| 發話 / EventSub | 否 | 是 |
| SOLID | 讀取層較乾淨 | `event_message` 上帝方法 |

## twitch_api 路徑索引

| 層 | 路徑 | 遷移目標 |
|----|------|----------|
| Ingress | `src/bot/chatbot.py`, `event_handlers.py` | `ingress-twitch-eventsub` |
| Ingress SA | `src/bridge/sa_bridge.py` | `ingress-sa-bridge` |
| Core | `src/runtime/events.py` | `pkg-bus` |
| Core | `src/runtime/controller.py`, `bot_manager.py` | `stream-app` |
| Identity | `src/auth/`, `account_service.py` | `identity-oauth` |
| Logic | `bot/chat_commands.py`, `utils/bot_responses.py` | `sub-bot-logic` |
| Egress | `send_message`, `throttle.py` | `twitch-connector` |
| Egress | `tts/` | `sub-tts` + `pkg-tts` |
| Egress | `runtime/subtitle.py` | `sub-visual` |
| LocalPC | `ui/main_window.py`, `chat_overlay_*` | `sub-show-overlay` |

入口：`main.py`、`scripts/first_time_auth.py`。

**缺口**：LLM、Discord、Web Dashboard、EventSub Webhook、虛擬角色管線、輸出安全層。

## 遷移對照

| twitch_api 現況 | 目標 | 難度 | SOLID |
|-----------------|------|------|-------|
| `RuntimeEventBus` | `pkg-bus` | 低 | D |
| `AppController` | `stream-app` | 低 | S |
| `TwitchBot` + Mixin | 拆 ingress / sub / connector | **高** | S, O |
| `auth/` | `identity-oauth` | 低 | I |
| `tts/message_filter` | `pkg-safety` 輸入 | 低 | L |
| `ui/chat_overlay_*` | `sub-show-overlay` | 中 | O |
| — | `pkg-events`, `sub-llm`, `sub-character-*` | 新建 | — |

### 遷移順序

1. 建立 `pkg-events` + `pkg-bus`，凍結 [events.md](events.md) 契約
2. `event_message` → 僅 normalize + publish `chat.message`
3. 抽出 `sub-bot-logic`、`twitch-connector`、`sub-tts` 為獨立訂閱者
4. yt/ttv ingress adapter 接入同一 schema
5. `sub-llm`、`sub-character-*` 以新 Sub 擴展（**O**）

每步通過 [solid.md 檢查清單](solid.md#新-repo--sub-檢查清單)。

## OAuth

→ [use-cases/04-oauth.md](use-cases/04-oauth.md)；權威來源 [`twitch_api/README.md`](../twitch_api/README.md)。

## 設計文件與實作 repo 關係

```
stream_helper/docs/     ← 規範（本 repo）
streamer-toolkit/       ← Phase 01 參考實作（姊妹 repo）
pkg-events/             ← 實作 events.md
sub-*/ingress-*/       ← 實作 modules.md + use-cases
stream-app/             ← 實作 App 啟用表
```

實作不得與設計文件衝突；契約變更須先改 `events.md` 再改程式。
