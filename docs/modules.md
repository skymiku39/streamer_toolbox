# 模組與產品組裝

模組目錄、產品 A～D、App 啟用表的**唯一來源**。Payload 見 [events.md](events.md)；repo 對應見 [packages.md](packages.md)。

## 模組一覽

| 模組 ID | 層 | 狀態 | 程序 / Package | 參考實作 |
|---------|-----|------|----------------|----------|
| `ingress-twitch-eventsub` | Ingress | 已有 | `ingress-twitch-eventsub` | `twitch_api` `bot/` |
| `ingress-yt-read` | Ingress | 已有 | `ingress-yt-read` | `packages/tubechat-lens` |
| `ingress-ttv-read` | Ingress | 已有 | `ingress-ttv-read` | `packages/ttvchat-lens` |
| `ingress-twitch-audio` | Ingress | 已有 | `ingress-twitch-audio` | `llm_twitchat` `ingest/` |
| `ingress-twitch-stream` | Ingress | 已有 | `ingress-twitch-stream` | Twitch GQL 直播 metadata |
| `ingress-local-audio` | Ingress | 已有 | `ingress-local-audio` | 本機麥克風 STT（開發用） |
| `ingress-discord` | Ingress | 已有 | `ingress-discord` | — |
| `stream-record` | Core | 已有 | `sub-stream-record` | L1 SQLite 記錄層 |
| `memory-worker` | Core | 已有 | `app.workers` | L2 定時摘要 → Chroma |
| `memory-board` | LocalPC | 已有 | `sub-memory-board` | 本機 HTTP 瀏覽 L2 摘要 |
| `io-log` | Core | 已有 | `sub-io-log` | `streamer-toolkit` `sub1` |
| `identity-oauth` | Identity | 已有 | `identity-oauth` | 本專案 `packages/identity-oauth` |
| `core-eventbus` | Core | 已有 | `bus` | `packages/bus` |
| `core-orchestrator` | Core | 已有 | `streamer-app` | `app/main.py` + `processes/` |
| `logic-commands` | Logic | 已有 | `sub-bot-logic` | `chat_commands.py` |
| `logic-keywords` | Logic | 已有 | `sub-bot-logic` | `bot_responses.py` |
| `logic-llm` | Logic | 已有 | `sub-llm` | 本專案（歷史參考 `llm_twitchat`） |
| `qa-memory-structured` | Logic | 已有 | `sub-qa-memory-structured` | `QA_MEMORY_MODE=structured` |
| `qa-memory-batch` | Logic | 已有 | `sub-qa-memory-batch` | `QA_MEMORY_MODE=batch` |
| `game-info` | Logic | 已有 | `game-info` | IGDB 遊戲資料注入 LLM |
| `safety-filter` | Logic | 部分 | `safety` | `sub-llm`、`sub-character-brain`、STT ingress 已接入；`sub-tts`/`sub-visual` 仍用自建 filter |
| `character-brain` | Logic | 已有 | `sub-character-brain` | — |
| `character-voice` | Egress | 已有 | `sub-character-voice` | — |
| `character-face` | Egress | 已有 | `sub-character-face` | VTS WebSocket |
| `character-stage` | LocalPC | 已有 | `sub-character-stage` | OBS WebSocket |
| `egress-chat-send` | Egress | 已有 | `twitch-connector` | `send_message` |
| `egress-tts` | Egress | 已有 | `sub-tts` | `tts/` |
| `egress-subtitle` | Egress | 已有 | `sub-visual` | `subtitle.py` |
| `local-dashboard` | Control | 規劃中 | Dashboard Shell | 見 [architecture/control-plane.md](architecture/control-plane.md)；承接 `system.*` 監控與模組分頁，**不作為業務 Sub** |
| `local-show` | LocalPC | 已有 | `sub-show-overlay` | overlay / desktop |
| `local-vts` | LocalPC | Future | — | VTS 整合目前嵌在 `sub-character-face` |
| `voice-clone` | LocalPC | 已有 | `voice-clone` | 離線語音克隆 CLI（OmniVoice）；可選、不接入 app/MQ |

## 產品定義

### 產品 A — 純 SHOW

| 模組 | 必要性 |
|------|--------|
| `ingress-yt-read` 或 `ingress-ttv-read` | Required |
| `core-eventbus`, `local-show` | Required |
| 其餘 | — |

→ [01-show.md](use-cases/01-show.md)

### 產品 B — 規則 BOT

| 模組 | 必要性 |
|------|--------|
| `ingress-twitch-eventsub`, `identity-oauth` | Required |
| `core-orchestrator`, `core-eventbus` | Required |
| `logic-commands`, `logic-keywords`, `egress-chat-send` | Required |
| `egress-tts`, `egress-subtitle`, `local-show`, `local-dashboard` | Optional |

→ [02-rule-bot.md](use-cases/02-rule-bot.md)

### 產品 C — LLM BOT

**完整定義**：產品 B 模組 + `logic-llm` + `safety-filter` + `ingress-twitch-audio`（建議）+ `ingress-twitch-stream`（建議）+ 記憶管線。

**實務上有兩種開法**（詳見 [operator-modes.md](operator-modes.md)）：

| 開法 | 含 `sub-bot-logic`？ | 典型啟動 |
|------|:--------------------:|----------|
| **精簡**（`getting-started` 預設） | 否 | `--stack ingress` + `--stack llm` |
| **完整** | 是 | `ingress-twitch-eventsub` + `sub-bot-logic` + `--stack llm` |

→ [03-llm-bot.md](use-cases/03-llm-bot.md) · 記憶管線詳見 [architecture/stream-memory-pipeline.md](architecture/stream-memory-pipeline.md)

### 產品 D — 虛擬角色

| 模組 | 必要性 |
|------|--------|
| `ingress-*`（至少一種） | Required |
| `core-eventbus`, `core-orchestrator` | Required |
| `character-brain`, `character-voice`, `character-face`, `character-stage` | Required |
| `safety-filter`（雙閘門，內嵌於 brain 或 `safety`） | Required |
| `egress-chat-send` | Optional（若要同步發聊天文字） |
| `identity-oauth` | 僅 EventSub ingress + 發話時 Required |
| `local-show` | Optional（同屏顯示觀眾彈幕） |
| `sub-bot-logic`, `sub-llm`, `sub-tts`（觀眾朗讀） | **不啟動** |

核心：訂閱 `character.turn` 的第二層管線，非 `chat.message` fan-out。→ [05-character.md](use-cases/05-character.md)

## App 層啟用表

`●` 必開 · `○` 可選 · `—` 不開

### 基礎設施

| 元件 | A | B | C | D |
|------|:-:|:-:|:-:|:-:|
| App | ○ | ● | ● | ● |
| MQ | ● | ● | ● | ● |
| `identity-oauth` | —¹ | ● | ● | —¹ |

¹ EventSub 或發話時改 ●

### Publisher

| Pub | topic | A | B | C | D |
|-----|-------|:-:|:-:|:-:|:-:|
| `ingress-yt/ttv-read` | `chat.message` | ● | —² | —² | ○ |
| `ingress-twitch-eventsub` | `chat.message` | ○ | ● | ●⁶ | ○ |
| 同上 | `eventsub.*` | — | ● | ● | — |
| `ingress-twitch-audio` | `stt.segment` | — | — | ○ | — |
| `ingress-twitch-stream` | `stream.metadata` | — | — | ○ | — |
| `ingress-local-audio` | `stt.segment` | — | — | ○³ | — |
| `ingress-discord` | `chat.message` | ○ | ○ | ○ | ○ |

² EventSub 不可用時，App **改啟** `ingress-ttv-read`（`twitch_api` `fallback_chat.py` 模式），不與 EventSub ingress 並行。

³ 本機麥克風 STT，開發／無 streamlink 時替代 `ingress-twitch-audio`。

### Subscriber

| Sub | topic | A | B | C | D |
|-----|-------|:-:|:-:|:-:|:-:|
| `sub-show-overlay` | `chat.message` | ● | ○ | ○ | ○ |
| `sub-visual` | `chat.message` | — | ○ | ○ | — |
| `sub-tts` | `chat.message` | — | ○ | ○ | — |
| `sub-bot-logic` | `chat.message`, `eventsub.*` | — | ● | ○⁵ | — |
| `sub-llm` | `chat.message`, `stt.segment`, `stream.metadata` | — | — | ● | — |
| `sub-stream-record` | `chat.message`, `stt.segment` | — | ○ | ○ | — |
| `sub-qa-memory-structured` | `memory.qa.record` | — | — | ○⁴ | — |
| `sub-qa-memory-batch` | `chat.reply` | — | — | ○⁴ | — |
| `sub-memory-board` | （HTTP 讀 DB） | — | — | ○ | — |
| `sub-io-log` | `chat.message`（診斷） | ○ | ○ | ○ | ○ |
| `sub-character-brain` | `chat.message` | — | — | — | ● |
| `sub-character-voice` | `character.turn` | — | — | — | ● |
| `sub-character-face` | `character.turn` | — | — | — | ● |
| `sub-character-stage` | `character.audio.ready`, `character.expression.ready` | — | — | — | ● |
| `twitch-connector` | `chat.reply` | — | ● | ● | ○ |
| `local-dashboard` | `system.*`（監控） | — | ○ | ○ | ○ |

⁴ 依 `QA_MEMORY_MODE` 擇一啟用；`--stack llm` 會啟動兩者，非對應模式者自動 idle 退出。

⁵ 產品 C **精簡**（`--stack ingress` + `--stack llm`）不啟動；**完整**版才需要 ●。

⁶ 產品 C **精簡**用 `--stack ingress`（內含 `ingress-ttv-read`）；**完整**版用 `ingress-twitch-eventsub`。

客製控制面板（UI 層）暫不納入啟用表；原則上可作 **Publisher** 將操作轉為 topic（契約待定）。

### Worker（非 MQ Sub）

| Worker | 職責 | A | B | C | D |
|--------|------|:-:|:-:|:-:|:-:|
| `app.workers` | L2 定時摘要 → `summaries` → Chroma | — | — | ○ | — |

### 啟動快照

```
A: ingress-read → MQ → sub-show
B: oauth → ingress-eventsub → MQ → sub-bot → connector
   （降級: ingress-ttv-read 取代 eventsub）
C: 精簡: --stack ingress + --stack llm（無 sub-bot-logic）
   完整: ingress-eventsub + sub-bot-logic + --stack llm + app.workers（可選）
   ingress stack: ingress-ttv-read, ingress-twitch-audio, ingress-twitch-stream, sub-stream-record
   llm stack: sub-llm, sub-qa-memory-*, twitch-connector
D: ingress → MQ → character-brain → character.turn → (voice + face) → stage → OBS
   可選: brain → chat.reply → connector；可選: sub-show 顯示彈幕
```

### CLI 啟動（現況）

編排以 `uv run python -m app.main` 為準；預定義 stack 見 `app/processes/stacks.py`：

```powershell
# 列出已註冊程序
uv run python -m app.main list

# 產品 A（Phase 01 smoke）
uv run python -m app.main run sub-io-log
uv run python -m app.main run ingress-ttv-read

# 產品 C（雙終端，詳見 getting-started.md）
uv run python -m app.main run --stack ingress
uv run python -m app.main run --stack llm
uv run python -m app.workers --llm-backend gemini   # L2 記憶 worker

# 產品 B（手動指定）
uv run python -m app.main run ingress-twitch-eventsub sub-bot-logic twitch-connector

# 產品 D（手動指定）
uv run python -m app.main run ingress-twitch-eventsub sub-character-brain sub-character-voice sub-character-face sub-character-stage
```

`--chat-fallback`（預設開啟）：含 `ingress-twitch-eventsub` 時，EventSub 聊天不可用會自動改啟 `ingress-ttv-read`。

### App 設定範例（規劃中，尚未實作）

下列 YAML 為**目標態**啟用表；現況請用上方 CLI。實作後將取代手動指定程序名。

#### 產品 D

```yaml
product: D

mq: { backend: inprocess }

publishers:
  ingress-twitch-eventsub: { enabled: true, channel: your_channel }

subscribers:
  sub-character-brain: { enabled: true, topics: [chat.message] }
  sub-character-voice: { enabled: true, topics: [character.turn] }
  sub-character-face: { enabled: true, topics: [character.turn] }
  sub-character-stage:
    enabled: true
    topics: [character.audio.ready, character.expression.ready]
  sub-show-overlay: { enabled: true, topics: [chat.message] }
  twitch-connector: { enabled: true, topics: [chat.reply] }
  sub-bot-logic: { enabled: false }
  sub-tts: { enabled: false }

identity: { oauth: { enabled: true, env_file: .env } }
```

#### 產品 B

```yaml
product: B

mq: { backend: rabbitmq, url: "${RABBITMQ_URL}" }

identity:
  oauth: { enabled: true, env_file: .env }

publishers:
  ingress-twitch-eventsub: { enabled: true, channel: your_channel }
  # 降級時改為:
  # ingress-ttv-read: { enabled: true, channel: your_channel }

subscribers:
  sub-bot-logic: { enabled: true, topics: [chat.message, eventsub.*] }
  twitch-connector: { enabled: true, topics: [chat.reply] }
  sub-show-overlay: { enabled: false }
  sub-tts: { enabled: false }
  sub-visual: { enabled: false }
  sub-io-log: { enabled: true, topics: [chat.message] }
```

#### 產品 C

```yaml
product: C

# 繼承產品 B publishers / subscribers，並加上:
publishers:
  ingress-twitch-audio: { enabled: true, channel: your_channel }

subscribers:
  sub-llm: { enabled: true, topics: [chat.message, stt.segment] }
```

## Topic 一覽

完整 payload：[events.md](events.md)

| Topic | Publisher | Subscriber |
|-------|-----------|------------|
| `chat.message` | ingress-* | show, tts, bot, llm, character-brain, stream-record |
| `eventsub.*` | ingress-twitch-eventsub | bot-logic |
| `stt.segment` | ingress-twitch-audio, ingress-local-audio | llm, stream-record |
| `stream.metadata` | ingress-twitch-stream | llm |
| `chat.reply` | bot, llm, character-brain | twitch-connector, qa-memory-batch |
| `memory.qa.record` | llm（structured 模式） | qa-memory-structured |
| `memory.summary.ready` | qa-memory-structured, workers | memory-board（規劃：notify） |
| `character.turn` | character-brain | character-voice, character-face |
| `character.audio.ready` | character-voice | character-stage |
| `character.expression.ready` | character-face | character-stage |
| `system.*` | 各元件 | dashboard, monitor |

## 選配速查

| 需求 | 加 |
|------|-----|
| 零 OAuth 看聊天 | `ingress-yt-read` / `ingress-ttv-read` |
| 規則 BOT | 產品 B 模組 |
| AI 文字回話 | 產品 C |
| 虛擬角色（TTS+表情+OBS） | 產品 D |
| 觀眾彈幕朗讀 | `sub-tts`（與產品 D 的 character-voice 不同） |
| 直播音訊 STT + LLM | `ingress-twitch-audio` + `sub-llm` |
| 本機麥克風 STT（開發） | `ingress-local-audio` + `sub-llm` |
| 直播遊戲 metadata 注入 LLM | `ingress-twitch-stream` + `game-info` |
| L1/L2 記憶管線 | `sub-stream-record` + `app.workers` + Chroma |
| Bot 問答長期記憶 | `QA_MEMORY_MODE=structured` 或 `batch` + 對應 `sub-qa-memory-*` |
| 瀏覽 L2 摘要 | `sub-memory-board` |
| EventSub 降級唯讀 | App 改啟 `ingress-ttv-read`，停 `ingress-twitch-eventsub` |

## 參考程式碼對照

| Package | 本專案路徑 / 歷史參考 |
|---------|---------------------|
| `ingress-ttv-read` | `packages/ttvchat-lens` |
| `ingress-yt-read` | `packages/tubechat-lens` |
| `ingress-twitch-eventsub` | [`twitch_api`](../twitch_api) `src/bot/chatbot.py`, `event_handlers.py` |
| `ingress-twitch-audio` | [`llm_twitchat`](../llm_twitchat) `services/ingest.py`, `ingest/stt_worker.py` |
| `ingress-twitch-stream` | Twitch GQL（Helix 補充 metadata） |
| `ingress-local-audio` | 本機 `sounddevice` + `faster-whisper` |
| `sub-bot-logic` | `twitch_api` `chat_commands.py`, `bot_responses.py`, `redemption_responses.py` |
| `sub-tts` | `twitch_api` `tts/` |
| `sub-show-overlay` | `twitch_api` `ui/chat_overlay_*` |
| `sub-visual` | `twitch_api` `runtime/subtitle.py` |
| `twitch-connector` | `twitch_api` `send_message`, `throttle.py` |
| `identity-oauth` | `packages/identity-oauth` + `scripts/first_time_auth.py` |
| `sub-llm` | `app/subscribers/sub_llm/`（歷史參考 `llm_twitchat`） |

## 相關文件

- [solid.md](solid.md) — 新模組檢查清單
- [packages.md](packages.md) — repo 劃分
- [deployment.md](deployment.md) — 運行部署
