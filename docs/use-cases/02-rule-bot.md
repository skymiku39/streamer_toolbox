# 產品 B：規則 BOT

| 項目 | 連結 |
|------|------|
| 模組 / 啟用 | [modules.md#產品-b--規則-bot](../modules.md#產品-b--規則-bot) |
| 事件 | [chat.message](../events.md#chatmessage)、[chat.reply](../events.md#chatreply) |
| OAuth | [04-oauth.md](04-oauth.md) |

對照 `twitch_api` [`event_handlers.event_message`](../../../twitch_api/src/bot/event_handlers.py)。

## As-Is（違反 SOLID **S**）

```mermaid
sequenceDiagram
    participant Twitch
    participant Ingress
    participant MQ
    participant UI
    participant TTS
    participant Logic
    participant Send

    Twitch->>Ingress: ChatMessage
    Ingress->>MQ: chat.message
    MQ->>UI: drain
    Note over Ingress,TTS: 同一 handler 內直接呼叫
    Ingress->>TTS: queue
    Ingress->>Logic: commands + keywords
    Logic->>Send: send_message
    Send->>Twitch: Helix
```

## To-Be（目標態）

```mermaid
sequenceDiagram
    participant Twitch
    participant Ingress
    participant MQ
    participant Show
    participant TTS
    participant Bot as sub_bot_logic
    participant Send as twitch_connector

    Twitch->>Ingress: ChatMessage
    Ingress->>MQ: publish chat.message
    par fan-out
        MQ->>Show: subscribe
        MQ->>TTS: subscribe
        MQ->>Bot: subscribe
    end
    Bot->>MQ: publish chat.reply
    MQ->>Send: subscribe
    Send->>Twitch: Helix
```

## twitch_api 對照

| 步驟 | 檔案 |
|------|------|
| 接收 | `bot/chatbot.py`, `event_handlers.py` |
| publish | `event_bus.emit(CHAT_MESSAGE)` |
| 指令 / 關鍵字 | `chat_commands.py`, `bot_responses.json` |
| 發話 | `send_message`, `throttle.py` |

## EventSub 非聊天事件

`eventsub.follow` 等由 ingress publish → `sub-bot-logic` 訂閱 → `chat.reply` 通知。見 [events.md#eventsub](../events.md#eventsub)。
