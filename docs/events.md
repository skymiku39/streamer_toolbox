# 事件契約（Topic & Payload）

**所有 Sub 只依賴本文件的 schema，不依賴 TwitchIO / PySide6 等框架類型**（SOLID **D**）。

版本欄位 `schema_version` 建議固定為 `1`，破壞性變更時遞增。

## Topic 註冊表

| Topic | Publisher | Subscriber | 產品 |
|-------|-----------|------------|------|
| `chat.message` | `ingress-*` | show, tts, bot, llm, character-brain | A～D |
| `eventsub.*` | `ingress-twitch-eventsub` | bot-logic | B, C |
| `stt.segment` | `ingress-twitch-audio` | llm, io-log（診斷） | C |
| `stt.status` / `stt.error` | `ingress-twitch-audio` | monitor（App） | C |
| `chat.reply` | bot, llm, character-brain | twitch-connector | B～D |
| `character.turn` | character-brain | character-voice, character-face | D |
| `character.audio.ready` | character-voice | character-stage | D |
| `character.expression.ready` | character-face | character-stage | D |
| `system.health` | 各 Sub | dashboard, monitor | 全部 |
| `system.error` | 各 Sub | dashboard, monitor | 全部 |

命名規則：`{domain}.{action}`；EventSub 事件為 `eventsub.{event_name}`（如 `eventsub.follow`）。

## `chat.message`

觀眾或系統聊天輸入（ingress normalize 後發布）。

```json
{
  "schema_version": 1,
  "topic": "chat.message",
  "platform": "youtube",
  "message_id": "abc123",
  "author_id": "UC...",
  "author_name": "觀眾暱稱",
  "login": "viewer_login",
  "content": "訊息正文",
  "timestamp": "2026-06-12T17:00:00+08:00",
  "channel": "channel_name",
  "badges": [],
  "emote_url_map": {},
  "reply": null,
  "raw": {}
}
```

| 欄位 | 類型 | 必填 | 說明 |
|------|------|:----:|------|
| `platform` | string | ✓ | `youtube` / `twitch` / `discord` |
| `message_id` | string | ✓ | 平台訊息 ID |
| `author_name` | string | ✓ | 顯示名稱 |
| `content` | string | ✓ | 正文 |
| `timestamp` | string | ✓ | ISO 8601 |
| `channel` | string | ○ | 頻道識別 |
| `badges`, `emote_url_map`, `reply` | object | ○ | 顯示用 |
| `raw` | object | ○ | ingress 原始資料；見下方 `raw` 約定 |

對齊來源：`yt_chat` / `ttv_chat` 的 `ChatMessage.to_dict()` + `platform`。

### `raw` 約定（跨平台）

Ingress 應在 `raw` 保留參考庫原始欄位，供 overlay / bot 選讀；**下游 Sub 不得硬依賴 `raw` 結構**（僅依賴本表必填欄位）。

| 來源 | 建議 `raw` 欄位 | 說明 |
|------|-----------------|------|
| `ttv_chat` / `ingress-ttv-read` | `message_type` | 如 `textMessage`、`sub`、`raid`、`bitsbadgetier`（IRC `USERNOTICE`） |
| `ttv_chat` | `amount`, `bits`, IRC tags | 訂閱／bits 等 metadata |
| `yt_chat` / `ingress-yt-read` | `message_type` | 如 `textMessage`、`superChat`、`superSticker`、`membershipItem` |
| `yt_chat` | `amount` | Super Chat 金額字串 |
| `ingress-twitch-eventsub` | 平台原始 payload | EventSub 回調 body |

**IRC 匿名路徑與 EventSub 路徑：** 非聊天事件在官方路徑發 `eventsub.*`；匿名 IRC（`ingress-ttv-read`）僅發 `chat.message` 並以 `raw.message_type` 區分，**不**偽造 `eventsub.*`。`sub-bot-logic` 須同時處理兩種來源。

## `eventsub.*`

Twitch EventSub 非聊天事件（**僅** `ingress-twitch-eventsub` 發布）。topic 為完整字串，例如 `eventsub.follow`。

### 已註冊事件類型

對照參考程式碼 `twitch_api` `bot/chatbot.py` `_build_subscription_list`：

| Topic | `event_type` | 備註 |
|-------|--------------|------|
| `eventsub.follow` | `follow` | |
| `eventsub.raid` | `raid` | |
| `eventsub.subscribe` | `subscribe` | 需 Affiliate/Partner |
| `eventsub.subscription_gift` | `subscription_gift` | 同上 |
| `eventsub.subscription_message` | `subscription_message` | 同上 |
| `eventsub.redemption` | `redemption` | 頻道點數兌換 |
| `eventsub.bits` | `bits` | |
| `eventsub.stream_online` | `stream_online` | |
| `eventsub.stream_offline` | `stream_offline` | |
| `eventsub.message_delete` | `message_delete` | |
| `eventsub.ban` | `ban` | |
| `eventsub.unban` | `unban` | |
| `eventsub.poll_begin` | `poll_begin` | |
| `eventsub.poll_progress` | `poll_progress` | |
| `eventsub.poll_end` | `poll_end` | |
| `eventsub.prediction_begin` | `prediction_begin` | |
| `eventsub.prediction_progress` | `prediction_progress` | |
| `eventsub.prediction_lock` | `prediction_lock` | |
| `eventsub.prediction_end` | `prediction_end` | |
| `eventsub.hype_train_begin` | `hype_train_begin` | |
| `eventsub.hype_train_progress` | `hype_train_progress` | |
| `eventsub.hype_train_end` | `hype_train_end` | |
| `eventsub.automod_message_hold` | `automod_message_hold` | |
| `eventsub.automod_message_update` | `automod_message_update` | |
| `eventsub.first_chat` | `first_chat` | **應用層合成**（開播後首位觀眾聊天），非原生 EventSub |

各類型 `payload` 欄位依 Twitch API；ingress  normalize 後至少含下列共用欄位：

```json
{
  "schema_version": 1,
  "topic": "eventsub.follow",
  "platform": "twitch",
  "event_type": "follow",
  "broadcaster_id": "...",
  "user_id": "...",
  "user_name": "...",
  "timestamp": "2026-06-12T17:00:00+08:00",
  "payload": {}
}
```

## `chat.reply`

邏輯層產出的發話意圖；**不直接呼叫平台 API**（由 connector Sub 負責）。

```json
{
  "schema_version": 1,
  "topic": "chat.reply",
  "platform": "twitch",
  "channel": "channel_name",
  "content": "BOT 回覆文字",
  "reply_to_message_id": null,
  "sender": "bot",
  "source": "logic-keywords",
  "correlation_id": "uuid-of-triggering-chat-message"
}
```

| 欄位 | 說明 |
|------|------|
| `source` | 產出者：`logic-commands` / `logic-keywords` / `logic-llm` / `character-brain` |
| `correlation_id` | 可選，追溯觸發的 `chat.message` 或 `eventsub.*` |

## `stt.segment`

直播音訊逐字稿片段（`ingress-twitch-audio` 發布；對照 `llm_twitchat` `ingest/`）。

```json
{
  "schema_version": 1,
  "topic": "stt.segment",
  "platform": "twitch",
  "channel": "channel_name",
  "segment_id": "uuid",
  "text": "辨識出的文字",
  "start_sec": 120.5,
  "end_sec": 125.0,
  "language": "zh",
  "confidence": 0.92,
  "highlight_score": 0.0,
  "timestamp": "2026-06-12T17:00:00+08:00"
}
```

| 欄位 | 說明 |
|------|------|
| `segment_id` | 片段唯一 ID |
| `start_sec` / `end_sec` | 相對直播開始的秒數（可選） |
| `highlight_score` | 聊天密度等衍生分數（可選，供摘要／高光） |

`stt.status`、`stt.error` 供 `ingress-twitch-audio` 回報載入／擷取狀態；由 App 訂閱 `system.*` 或專用 monitor 處理，**不**進入 `chat.reply` 管線。

## `character.turn`

產品 D：一輪角色回應的**同步錨點**（brain 發布，voice/face 訂閱）。

```json
{
  "schema_version": 1,
  "topic": "character.turn",
  "turn_id": "uuid",
  "correlation_id": "uuid-of-chat-message",
  "text": "角色要說的話",
  "emotion": "happy",
  "emotion_intensity": 0.8,
  "language": "zh-TW",
  "timestamp": "2026-06-12T17:00:00+08:00"
}
```

| 欄位 | 說明 |
|------|------|
| `turn_id` | 本輪唯一 ID，audio/face/stage 事件須引用 |
| `emotion` | 表情驅動用標籤（如 `neutral` / `happy` / `angry`） |
| `text` | 已通過安全層的文字；同時可 publish 精簡版至 `chat.reply` |

## `character.audio.ready`

```json
{
  "schema_version": 1,
  "topic": "character.audio.ready",
  "turn_id": "uuid",
  "audio_path": "/path/or/url",
  "duration_ms": 3200,
  "visemes": []
}
```

## `character.expression.ready`

```json
{
  "schema_version": 1,
  "topic": "character.expression.ready",
  "turn_id": "uuid",
  "driver": "vts",
  "parameters": { "mouth_smile": 0.9 }
}
```

## `system.health` / `system.error`

供 App monitor 與 dashboard；各 Sub 可選發布。

```json
{
  "schema_version": 1,
  "topic": "system.health",
  "component": "sub-bot-logic",
  "status": "ok",
  "timestamp": "2026-06-12T17:00:00+08:00",
  "detail": {}
}
```

## 實作約定

| 規則 | 說明 |
|------|------|
| 序列化 | JSON；MQ 傳輸統一 UTF-8 |
| 驗證 | `pkg-events` 提供 pydantic/dataclass 驗證 |
| 向後相容 | 只加 optional 欄位；刪欄位須 bump `schema_version` |
| 禁止 | Sub 間傳遞框架原生物件（如 TwitchIO `ChatMessage`） |

## 相關文件

- [modules.md](modules.md) — 誰 publish / subscribe
- [packages.md](packages.md) — `pkg-events` 定義處
- [solid.md](solid.md) — 依賴反轉
