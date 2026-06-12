# 事件契約（Topic & Payload）

**所有 Sub 只依賴本文件的 schema，不依賴 TwitchIO / PySide6 等框架類型**（SOLID **D**）。

版本欄位 `schema_version` 建議固定為 `1`，破壞性變更時遞增。

## Topic 註冊表

| Topic | Publisher | Subscriber | 產品 |
|-------|-----------|------------|------|
| `chat.message` | `ingress-*` | show, tts, bot, llm, character-brain | A～D |
| `eventsub.*` | `ingress-twitch-eventsub` | bot-logic | B, C |
| `chat.reply` | bot, llm, character-brain | twitch-connector | B～D |
| `sa.message` | `ingress-sa-bridge` | bot-logic | B, C（SA 模式） |
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
| `platform` | string | ✓ | `youtube` / `twitch` / `discord` / `sa` |
| `message_id` | string | ✓ | 平台訊息 ID |
| `author_name` | string | ✓ | 顯示名稱 |
| `content` | string | ✓ | 正文 |
| `timestamp` | string | ✓ | ISO 8601 |
| `channel` | string | ○ | 頻道識別 |
| `badges`, `emote_url_map`, `reply` | object | ○ | 顯示用 |
| `raw` | object | ○ | ingress 原始資料，Sub 不應依賴其結構 |

對齊來源：`yt_chat` / `ttv_chat` 的 `ChatMessage.to_dict()` + `platform`。

## `eventsub.*`

Twitch EventSub 非聊天事件。topic 為完整字串，例如 `eventsub.follow`。

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
| `correlation_id` | 可選，追溯觸發的 `chat.message` |

## `sa.message`

Stream Avatars 多平台 ingress。結構對齊 SA bridge 輸出，normalize 後與 `chat.message` 盡量一致，並設 `platform: "sa"`。

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
