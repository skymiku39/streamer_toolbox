# 開發環境設定

本 repo 同時包含設計文件（`docs/`）與 **stream-core** 實作（`pkg-*` 等 workspace package）。契約以 [events.md](events.md) 為準。

## 前置需求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker Desktop（RabbitMQ 本地開發用）

## 初次設定

```powershell
cd streamer_toolbox
uv sync
copy .env.example .env
```

編輯 `.env` 依需要調整（Phase 01 至少需要 `TWITCH_CHANNEL`）。

## RabbitMQ

```powershell
docker compose up -d
```

管理介面：http://localhost:15672（guest / guest）

## 執行測試

```powershell
uv run pytest
uv run ruff check .
```

## Workspace 結構

```
streamer_toolbox/
├── docs/              # 設計文件
├── pkg-events/        # 事件 schema（對齊 events.md）
├── pkg-bus/           # EventBus Protocol + MQ adapter
├── docker-compose.yml
└── pyproject.toml     # uv workspace 根
```

Phase 01 後續將加入 `ingress-twitch-chat`、`sub-io-log`。參考實作見姊妹專案 [streamer-toolkit](references/streamer-toolkit.md)。

## 設計約束

實作須遵守 [solid.md](solid.md) 與 [events.md](events.md)。契約變更先改文件，再改 `pkg-events`。
