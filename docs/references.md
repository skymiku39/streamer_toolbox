# 參考專案與遷移

本文件描述 **streamer-toolbox**（本專案，To-be：`ingress-*` / `sub-*`）與外部程式碼的對照關係。

## 術語

| 術語 | 含義 |
|------|------|
| **本專案** | `streamer_toolbox`：設計文件（`docs/`）與 stream-core 實作（`packages/` 內 `bus`、`events` 等 workspace package） |
| **姊妹專案** | 僅 [`streamer-toolkit`](../streamer-toolkit)：早期 Phase 01 Pub/Sub 架構參考 |
| **參考程式碼** | `twitch_api`、`llm_twitchat` 等：歷史 As-is，供對照邏輯；**執行期不依賴**。`ttvchat-lens`、`tubechat-lens` 已收編至 `packages/` |
| **Sub** | Pub/Sub 架構中的 **Subscriber package**（`sub-io-log`、`sub-llm` 等），非 Git submodule |

## 姊妹專案

| 專案 | 路徑 | 用途 |
|------|------|------|
| streamer-toolkit | [`../streamer-toolkit`](../streamer-toolkit) | 早期 Phase 01 RabbitMQ Pub/Sub 架構參考；本專案已實作對齊設計的版本 |

詳見 [references/streamer-toolkit.md](references/streamer-toolkit.md)。

## 參考程式碼總覽

下列 repo 為**參考用程式**，方便拆分或建立本專案各模組與邏輯；目標是演進為本專案內的 `ingress-*` / `sub-*` package，而非與本專案並列的姊妹專案。

| 專案 | 路徑 | PyPI / 套件名 | 用途 | 本專案現況 |
|------|------|---------------|------|------------|
| twitch-oauth-bot | [`../twitch_api`](../twitch_api) | `twitch-oauth-bot` | 全功能 Twitch BOT（歷史 As-is） | 邏輯已遷移至 `app/` + `identity-oauth` |
| TubeChat Lens | `packages/tubechat-lens` | `tubechat-lens` | YouTube 直播聊天唯讀 | ✅ `ingress-yt-read` |
| ttvchat-lens | `packages/ttvchat-lens` | `ttvchat-lens` | Twitch IRC 匿名唯讀 | ✅ `ingress-ttv-read` |
| llm-twitchat | [`../llm_twitchat`](../llm_twitchat) | `llm-twitchat` | 歷史 STT + Gemini Web App | ✅ 演進為 `sub-llm` + `ingress-twitch-audio` |

## 模組依賴關係

```mermaid
flowchart TB
    subgraph read [唯讀 Ingress — 已收編]
        YT[packages/tubechat-lens]
        TTV[packages/ttvchat-lens]
    end

    subgraph legacy [歷史參考 As-is]
        API[twitch_api]
        LLM[llm_twitchat]
    end

    subgraph sibling [姊妹專案]
        TK[streamer-toolkit]
    end

    subgraph design [streamer-toolbox 本專案 To-be]
        MQ[(MQ)]
        Ingress[ingress-*]
        Sub[sub-*]
    end

    YT -->|ChatMessage schema| Ingress
    TTV -->|ChatMessage schema| Ingress
    API -.->|歷史對照| Ingress
    LLM -.->|已 MQ 化| Sub
    TK -.->|Phase 01 可執行範本| Ingress
    Ingress --> MQ --> Sub
```

| 關係 | 說明 |
|------|------|
| `tubechat-lens` / `ttvchat-lens` | 已收編於 `packages/`；`uv sync` 不需外部 repo |
| `twitch_api` → `ingress-ttv-read` | EventSub 不可用時 App **改啟** `ingress-ttv-read`（匿名 IRC 降級） |
| `llm_twitchat` | 歷史獨立 App；現由 `sub-llm` + `ingress-twitch-audio` 取代 |
| 參考程式 → streamer-toolbox | 歷史 As-is 對照；執行期僅依賴本 repo workspace |
| streamer-toolkit → streamer-toolbox | 姊妹專案；早期 Pub/Sub 架構參考 |

### streamer-toolkit（姊妹專案）

早期 Phase 01 架構參考：Twitch IRC（匿名）→ RabbitMQ fanout → 多 Sub（檔案 log、web UI）。與 `ttv_chat` 同為 IRC 匿名讀取，但 toolkit 為自包含實作，曾示範 Pub/Sub 管線與 process registry 擴充模式；**正式實作已移至本專案**。

詳見 [references/streamer-toolkit.md](references/streamer-toolkit.md)。

### yt_chat / tubechat-lens（已收編）

| 項目 | 內容 |
|------|------|
| 本專案路徑 | `packages/tubechat-lens/` |
| 套件 | `tubechat_lens` |
| 程序 | `ingress-yt-read` |

歷史上游 repo 為 `yt_chat`；現已 vendored，無需另行 clone。

### ttv_chat / ttvchat-lens（已收編）

| 項目 | 內容 |
|------|------|
| 本專案路徑 | `packages/ttvchat-lens/` |
| 套件 | `ttvchat_lens` |
| 程序 | `ingress-ttv-read` |

歷史上游 repo 為 `ttv_chat`；現已 vendored，無需另行 clone。

### twitch_api（Twitch OAuth Bot）

| 項目 | 內容 |
|------|------|
| 連線 | EventSub + OAuth（主路徑）；降級時委派 `ttvchat_lens` |
| 能力 | 發話、指令、關鍵字、TTS、字幕、雙帳號、Overlay、Helix API |
| 執行期 | 單機 `RuntimeEventBus` + Bot thread + PySide6 UI + overlay 子進程 |
| 設計角色 | 產品 B As-is 基準；逐步拆為 `ingress-twitch-eventsub`、`sub-bot-logic`、`sub-tts`、`sub-show-overlay`、`twitch-connector`、`identity-oauth` |

#### twitch_api vs ttv_chat

| | ttv_chat | twitch_api |
|---|----------|------------|
| 連線 | IRC 匿名 | EventSub + OAuth（fallback → `ttvchat_lens`） |
| 發話 / EventSub | 否 | 是（fallback 時唯讀） |
| SOLID | 讀取層乾淨 | `event_message` 上帝方法（遷移目標：僅 normalize + publish） |

**LLM 已移出：** `!ask` / `!summary` 等 AI 問答不再內建於本 Bot，改由 [`llm_twitchat`](../llm_twitchat) 獨立提供。

### llm_twitchat

| 項目 | 內容 |
|------|------|
| 啟動 | `uv run llm-twitchat`；Web UI `http://127.0.0.1:1425`、WS `ws://127.0.0.1:8767` |
| 輸入 | 直播音訊 STT（streamlink + faster-whisper）+ Twitch IRC 聊天（內建，匿名） |
| 輸出 | Gemini 問答、摘要、高光時段；**不**代發 Twitch 訊息 |
| 執行期 | 單機 in-process `EventBus`（`core/event_bus.py`） |
| 設計角色 | 產品 C **As-is** 參考；To-be 已於本專案實作為 `sub-llm` + `ingress-twitch-audio` / `ingress-twitch-stream` |

詳見 [references/llm-twitchat.md](references/llm-twitchat.md)、[use-cases/03-llm-bot.md](use-cases/03-llm-bot.md)。

## Sub / Ingress 與參考程式對照

Subscriber（`sub-*`）與 Publisher（`ingress-*`）的 As-is 參考見 [packages.md#subscriber-package](packages.md#subscriber-package)。

| To-be package | 參考 As-is | 備註 |
|---------------|------------|------|
| `ingress-yt-read` | `packages/tubechat-lens` | workspace `tubechat_lens` |
| `ingress-ttv-read` | `packages/ttvchat-lens` | workspace `ttvchat_lens` |
| `ingress-twitch-eventsub` | `twitch_api` `bot/` | EventSub 主路徑 |
| `sub-bot-logic` | `twitch_api` `chat_commands.py`、`bot_responses.py` | 規則 BOT |
| `sub-tts` | `twitch_api` `tts/` | 觀眾彈幕朗讀 |
| `sub-show-overlay` | `twitch_api` `ui/chat_overlay_*` | |
| `sub-visual` | `twitch_api` `runtime/subtitle.py` | |
| `twitch-connector` | `twitch_api` `send_message`、`throttle.py` | |
| `identity-oauth` | 本專案 `packages/identity-oauth` | ✅ 含 bootstrap |
| `sub-llm` | `llm_twitchat` | **已 MQ 化**；邏輯見 `app/subscribers/sub_llm/` |
| `ingress-twitch-audio` | `llm_twitchat` `ingest/` | STT → `stt.segment` |
| `ingress-twitch-stream` | Twitch GQL | 直播 metadata → `stream.metadata` |
| `ingress-discord` | — | 已實作於本專案 |
| `sub-character-*` | — | 已實作於本專案（產品 D） |
| `sub-io-log` | streamer-toolkit `sub1` | 診斷 Sub，留本專案 |

## twitch_api 路徑索引

| 層 | 路徑 | 遷移目標 |
|----|------|----------|
| Ingress | `src/bot/chatbot.py`, `event_handlers.py` | `ingress-twitch-eventsub` |
| Ingress fallback | `packages/ttvchat-lens` | `ingress-ttv-read`（唯讀保底） |
| Core | `src/runtime/events.py` | `bus` |
| Core | `src/runtime/controller.py`, `bot_manager.py` | `streamer-app` |
| Identity | `src/auth/`, `account_service.py` | `identity-oauth` + `scripts/first_time_auth.py` |
| Logic | `bot/chat_commands.py`, `utils/bot_responses.py` | `sub-bot-logic` |
| Egress | `send_message`, `throttle.py` | `twitch-connector` |
| Egress | `tts/` | `sub-tts` + `tts` |
| Egress | `runtime/subtitle.py` | `sub-visual` |
| LocalPC | `ui/main_window.py`, `chat_overlay_*` | `sub-show-overlay` |

入口（歷史）：`twitch_api/main.py`。本專案：`scripts/first_time_auth.py`、`uv run python -m identity_oauth`。

**缺口（尚未有參考程式或仍待加強）：** Web Dashboard（`local-dashboard` 暫緩）、EventSub Webhook 獨立 ingress、`safety` 輸出閘門全面統一（`sub-tts`/`sub-visual` 仍用自建 filter）、YAML 產品設定編排。

**已於本專案實作（原列缺口）：** `ingress-discord`、`sub-llm`（MQ）、`sub-character-*`、`safety` 輸入閘門（`sub-llm`、`sub-character-brain`、STT ingress）。

## 遷移對照

| twitch_api 現況 | 目標 | 難度 | SOLID |
|-----------------|------|------|-------|
| `RuntimeEventBus` | `bus` | 低 | D |
| `AppController` | `streamer-app` | 低 | S |
| `TwitchBot` + Mixin | 拆 ingress / sub / connector | **高** | S, O |
| `auth/` | `identity-oauth` | 低 | I |
| `tts/message_filter` | `safety` 輸入（部分；TTS 仍自建） | 低 | L |
| `ui/chat_overlay_*` | `sub-show-overlay` | 中 | O |
| — | `events`, `sub-character-*` | 新建 | — |
| `llm_twitchat`（獨立） | `sub-llm` + STT/metadata ingress | 中 | S, O |

### 遷移順序

1. ~~建立 `events` + `bus`，凍結 [events.md](events.md) 契約~~ ✅
2. ~~`event_message` → 僅 normalize + publish `chat.message`~~ ✅（`ingress-twitch-eventsub`）
3. ~~抽出 `sub-bot-logic`、`twitch-connector`、`sub-tts` 為獨立訂閱者~~ ✅
4. ~~`yt_chat` / `ttv_chat` ingress adapter 接入同一 schema~~ ✅
5. ~~`llm_twitchat` 的 LLM 路徑演進為 `sub-llm`~~ ✅
6. ~~`sub-character-*` 以新 Sub 擴展~~ ✅
7. **進行中**：YAML 產品設定編排、`safety` 全面統一、EventSub Webhook ingress

每步通過 [solid.md 檢查清單](solid.md#新-repo--sub-檢查清單)。

## OAuth

→ [use-cases/04-oauth.md](use-cases/04-oauth.md)；權威來源 [architecture/identity-auth.md](architecture/identity-auth.md)。

## 本專案與外部程式關係

```
streamer_toolbox/          ← 本專案（單 repo 自包含）
  packages/ttvchat-lens/   ← 已收編
  packages/tubechat-lens/  ← 已收編
  packages/identity-oauth/ ← OAuth runtime + bootstrap
streamer-toolkit/          ← 姊妹專案：Phase 01 架構參考（非執行依賴）
twitch_api/                ← 歷史參考：產品 B As-is
llm_twitchat/              ← 歷史參考：產品 C As-is
```

實作不得與設計文件衝突；契約變更須先改 `events.md` 再改程式。
