# 模組與產品組裝

模組目錄、產品 A～D、App 啟用表的**唯一來源**。Payload 見 [events.md](events.md)；repo 對應見 [packages.md](packages.md)。

## 模組一覽

| 模組 ID | 層 | 狀態 | Package | 參考實作 |
|---------|-----|------|---------|----------|
| `ingress-twitch-eventsub` | Ingress | 已有 | `ingress-twitch-eventsub` | `twitch_api` `bot/` |
| `ingress-sa-bridge` | Ingress | 已有 | `ingress-sa-bridge` | `twitch_api` `bridge/` |
| `ingress-yt-read` | Ingress | 已有 | `ingress-yt-read` | `yt_chat` |
| `ingress-ttv-read` | Ingress | 已有 | `ingress-ttv-read` | `ttv_chat` |
| `ingress-discord` | Ingress | Future | `ingress-discord` | — |
| `identity-oauth` | Identity | 已有 | `identity-oauth` | `twitch_api` `auth/` |
| `core-eventbus` | Core | 已有 | `pkg-bus` | `runtime/events.py` |
| `core-orchestrator` | Core | 已有 | `stream-app` | `runtime/controller.py` |
| `logic-commands` | Logic | 已有 | `sub-bot-logic` | `chat_commands.py` |
| `logic-keywords` | Logic | 已有 | `sub-bot-logic` | `bot_responses.py` |
| `logic-llm` | Logic | 已有（As-is） | `sub-llm` | `llm_twitchat` |
| `safety-filter` | Logic | 部分 | `pkg-safety` | `tts/message_filter.py` |
| `character-brain` | Logic | Future | `sub-character-brain` | — |
| `character-voice` | Egress | Future | `sub-character-voice` | — |
| `character-face` | Egress | Future | `sub-character-face` | — |
| `character-stage` | LocalPC | Future | `sub-character-stage` | — |
| `egress-chat-send` | Egress | 已有 | `twitch-connector` | `send_message` |
| `egress-tts` | Egress | 已有 | `sub-tts` | `tts/` |
| `egress-subtitle` | Egress | 已有 | `sub-visual` | `subtitle.py` |
| `local-dashboard` | LocalPC | 已有 | `stream-app` UI | `ui/main_window.py` |
| `local-show` | LocalPC | 部分 | `sub-show-overlay` | overlay / desktop |
| `local-vts` | LocalPC | Future | — | — |

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
| `egress-tts`, `egress-subtitle`, `local-show`, `local-dashboard`, `ingress-sa-bridge` | Optional |

→ [02-rule-bot.md](use-cases/02-rule-bot.md)

### 產品 C — LLM BOT

產品 B Required + `logic-llm` + `safety-filter`（輸入+輸出）。

→ [03-llm-bot.md](use-cases/03-llm-bot.md)

### 產品 D — 虛擬角色

| 模組 | 必要性 |
|------|--------|
| `ingress-*`（至少一種） | Required |
| `core-eventbus`, `core-orchestrator` | Required |
| `character-brain`, `character-voice`, `character-face`, `character-stage` | Required |
| `safety-filter`（雙閘門，內嵌於 brain 或 `pkg-safety`） | Required |
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
| `ingress-yt/ttv-read` | `chat.message` | ● | — | — | ○ |
| `ingress-twitch-eventsub` | `chat.message` | ○ | ● | ● | ○ |
| 同上 | `eventsub.*` | — | ● | ● | — |
| `ingress-sa-bridge` | `sa.message` | — | ○ | ○ | — |

### Subscriber

| Sub | topic | A | B | C | D |
|-----|-------|:-:|:-:|:-:|:-:|
| `sub-show-overlay` | `chat.message` | ● | ○ | ○ | ○ |
| `sub-visual` | `chat.message` | — | ○ | ○ | — |
| `sub-tts` | `chat.message` | — | ○ | ○ | — |
| `sub-bot-logic` | `chat.message`, `eventsub.*` | — | ● | ● | — |
| `sub-llm` | `chat.message` | — | — | ● | — |
| `sub-character-brain` | `chat.message` | — | — | — | ● |
| `sub-character-voice` | `character.turn` | — | — | — | ● |
| `sub-character-face` | `character.turn` | — | — | — | ● |
| `sub-character-stage` | `character.audio.ready`, `character.expression.ready` | — | — | — | ● |
| `twitch-connector` | `chat.reply` | — | ● | ● | ○ |
| `local-dashboard` | `system.*` | — | ○ | ○ | ○ |

### 啟動快照

```
A: ingress-read → MQ → sub-show
B: oauth → ingress-eventsub → MQ → sub-bot → connector
C: B + sub-llm
D: ingress → MQ → character-brain → character.turn → (voice + face) → stage → OBS
   可選: brain → chat.reply → connector；可選: sub-show 顯示彈幕
```

### App 設定範例（產品 D）

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

完整產品 B 範例見上文 `product: B` 區塊（與先前相同）。

## Topic 一覽

完整 payload：[events.md](events.md)

| Topic | Publisher | Subscriber |
|-------|-----------|------------|
| `chat.message` | ingress-* | show, tts, bot, llm, character-brain |
| `eventsub.*` | ingress-twitch-eventsub | bot-logic |
| `chat.reply` | bot, llm, character-brain | twitch-connector |
| `character.turn` | character-brain | character-voice, character-face |
| `character.audio.ready` | character-voice | character-stage |
| `character.expression.ready` | character-face | character-stage |
| `sa.message` | ingress-sa-bridge | bot-logic |
| `system.*` | 各元件 | dashboard, monitor |

## 選配速查

| 需求 | 加 |
|------|-----|
| 零 OAuth 看聊天 | `ingress-yt-read` / `ingress-ttv-read` |
| 規則 BOT | 產品 B 模組 |
| AI 文字回話 | 產品 C |
| 虛擬角色（TTS+表情+OBS） | 產品 D |
| 觀眾彈幕朗讀 | `sub-tts`（與產品 D 的 character-voice 不同） |

## 相關文件

- [solid.md](solid.md) — 新模組檢查清單
- [packages.md](packages.md) — repo 劃分
- [deployment.md](deployment.md) — 運行部署
