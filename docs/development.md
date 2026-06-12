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

若本機**尚未**有 RabbitMQ 在跑：

```powershell
docker compose up -d
```

管理介面：http://localhost:15672（guest / guest）

若姊妹專案 `streamer-toolkit` 已啟動 `docker compose up -d`，其容器會佔用 **5672 / 15672**，本 repo **不必再啟一份**，`.env` 的 `RABBITMQ_URL` 直接連 `127.0.0.1:5672` 即可。

## 本 repo 目前能跑什麼

| 指令 | 是否可用 | 說明 |
|------|:--------:|------|
| `uv run pytest` | ✓ | `pkg-events`、`pkg-bus` 單元測試 |
| `uv run python -m app.main run` | ✗ | **本 repo 沒有 `app` 模組**；完整管線請到 `../streamer-toolkit` |
| `docker compose up -d` | △ | 僅在 5672 未被佔用時需要 |

## 端對端實測（Twitch → MQ → log / Web UI）

請在**姊妹專案**執行，勿在 `streamer_toolbox` 目錄：

```powershell
cd ..\streamer-toolkit
uv sync
copy .env.example .env   # 設定 TWITCH_CHANNEL
# RabbitMQ 若已在跑可略過 docker compose
uv run python -m app.main run
```

詳見 [references/streamer-toolkit.md](references/streamer-toolkit.md)。

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

## 常見問題

### `ModuleNotFoundError: No module named 'app'`

在 `streamer_toolbox` 執行了 `streamer-toolkit` 的指令。本 repo 尚無 `app/main.py`；請 `cd ..\streamer-toolkit` 再跑 `uv run python -m app.main run`。

### `Bind for 0.0.0.0:5672 failed: port is already allocated`

已有 RabbitMQ 佔用 5672（常見為 `streamer-toolkit-rabbitmq-1`）。**不需**在本 repo 再 `docker compose up`；確認 `docker ps` 有 rabbitmq 容器在跑即可。若要改由本 repo 啟動，先停止舊容器：`docker stop streamer-toolkit-rabbitmq-1`。
