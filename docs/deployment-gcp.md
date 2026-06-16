# GCP 部署（LLM Bot — 純文字 AI 問答）

將 **Backend 全數部署在 GCE VM**，實況機**不必**跑 Python stack。對應 [operator-modes.md § AI 問答](operator-modes.md#方案ai-問答) 的**純文字**路線：`ingress-chat` stack 收 Twitch 聊天與直播 metadata，`llm` stack 處理 `!ask` 並經 `twitch-connector` 發話。

> **範圍**：本 runbook **不含**雲端 STT（`ingress-twitch-audio`）、本機麥克風 STT、語音記憶摘要。若需 STT，見 [control-plane.md § T4 Hybrid STT](architecture/control-plane.md#t4--hybrid-stt)。

| 文件 | 內容 |
|------|------|
| [deployment.md](deployment.md) | Pub/Sub 部署邊界 |
| [architecture/control-plane.md § 部署拓撲](architecture/control-plane.md#部署拓撲) | T2 All-GCP、T4 Hybrid 等拓撲對照 |

本文件為 **T2 All-GCP（純文字）** 的 GCE runbook（Compose、Secret Manager、bootstrap）。

## 架構

```mermaid
flowchart TB
    subgraph local [本機一次性]
        OAuth["scripts/first_time_auth.py"]
        Secret["GCP Secret Manager"]
        OAuth --> Secret
    end

    subgraph gce [GCE VM]
        Compose["docker compose gcp"]
        MQ[(RabbitMQ)]
        Ing[ingress-chat stack]
        Llm[llm-stack]
        Data["/data 持久磁碟"]
        Compose --> MQ
        Compose --> Ing
        Compose --> Llm
        Ing --> Data
        Llm --> Data
    end

    Twitch[Twitch IRC / Helix] --> Ing
    Llm --> Twitch
    Gemini[Google AI API] --> Llm
    Secret -.-> Ing
    Secret -.-> Llm
```

| 元件 | 位置 |
|------|------|
| RabbitMQ、`ingress-ttv-read`、`ingress-twitch-stream`、`sub-stream-record`、`sub-llm`、`twitch-connector` | GCE VM（[deploy/docker-compose.gcp.yml](../deploy/docker-compose.gcp.yml)） |
| SQLite、Chroma、日誌 | VM 持久磁碟 `/data` |
| 知識庫 md | `/config/knowledge/` |
| OAuth 首次授權 | **本機**（瀏覽器 callback） |
| OBS / overlay | 不在本方案範圍（實況機可完全不裝 Bot） |

**不部署**：`ingress-twitch-audio`、`ingress-local-audio`、`app.workers`（L2 摘要，預設不啟用）。

> **長期記憶（RAG）限制**：T2 預設不跑 `app.workers`，因此 **L2 摘要不會產生**，Chroma `kb_memory` 會是空的——`!ask` 只能用短期上下文 buffer、`LLM_KNOWLEDGE_PATH` 靜態知識與（Gemini）Google Search，**沒有跨時段的長期直播記憶**。短期記憶（程序內 buffer 與可選的 `kb_shortterm`）不受影響。
>
> 若需要本場／跨時段的長期問答記憶，請啟用下方「[chat-only 記憶 worker](#chat-only-記憶-worker可選)」；否則請把「長期記憶不可用」視為此純文字方案的已知邊界。

### chat-only 記憶 worker（可選）

純文字方案沒有 STT，因此 worker 只需摘要聊天室。新增第三個 compose service 常駐執行：

```bash
uv run python -m app.workers --llm-backend gemini
```

搭配 `.env`：`RECORD_MODE=chat`（只記聊天）、`MEMORY_LLM_BACKEND=gemini`、`MEMORY_INTERVAL_MINUTES=30`。worker 會把 SQLite `summaries` 同步到 Chroma `kb_memory`，`sub-llm` 才會在 `!ask` 時讀到長期記憶（需 `LLM_MEMORY_FROM_DB=true`，預設即是）。

## 前置需求

| 項目 | 說明 |
|------|------|
| GCP 專案 | 啟用 Compute Engine、Secret Manager API |
| 本機 | 已完成 [getting-started.md §3](getting-started.md#第-3-層實際跑-llm-bota-問答方案) OAuth 與 `.env` 驗證 |
| VM 規格（建議） | `e2-standard-2`（2 vCPU / 8 GB）或 `e2-small`；50 GB 持久磁碟 |
| 區域 | 如 `asia-east1`（依延遲調整） |

純文字路線無 Whisper 負載，無需 `e2-standard-4` 等 STT 規格。

## 1. 本機：OAuth 與 Secret

在本機 Windows／Linux 開發機完成 Twitch OAuth（**不要在 VM 內跑瀏覽器授權**）：

```powershell
uv run python scripts/first_time_auth.py --role channel
uv run python scripts/first_time_auth.py --role bot
```

確認 `.env` 至少含：

- `TWITCH_CHANNEL`
- `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET`
- `TWITCH_BOT_REFRESH_TOKEN` / `TWITCH_BOT_ID`
- `GOOGLE_AI_API_KEY`
- `LLM_BACKEND=gemini`
- `RECORD_MODE=chat`（純文字；勿設 `both` 或 `stt`）

將**機密內容**寫入 GCP Secret Manager（單一 secret，內容為完整 `.env` 或精簡版）：

```bash
# 參考欄位：deploy/.env.gcp.example
gcloud secrets create streamer-toolbox-env --data-file=.env
# 更新時：
gcloud secrets versions add streamer-toolbox-env --data-file=.env
```

VM 上的 service account 需具備 `roles/secretmanager.secretAccessor`。

## 2. 建立 GCE VM

1. 建立 VM（Debian 12 或 Ubuntu 22.04+）。
2. 附加持久磁碟，掛載至 `/data`（格式化一次後寫入 `/etc/fstab`）。
3. 建立 `/config` 目錄（可與 `/data` 同碟或獨立掛載）。
4. SSH 進 VM 後執行 bootstrap：

```bash
export STREAMER_REPO_URL=https://github.com/<you>/streamer_toolbox.git
sudo bash deploy/bootstrap_vm.sh
```

`bootstrap_vm.sh` 會安裝 Docker、建立 `/data`、`/config`、`/run/secrets` 目錄。

## 3. 知識庫

將頻道知識庫複製到 VM：

```bash
scp config/knowledge/{TWITCH_CHANNEL}.md user@<VM_IP>:/config/knowledge/
```

首次部署後可執行容器內驗證（選用）：

```bash
docker compose -f deploy/docker-compose.gcp.yml run --rm llm-stack \
  python scripts/verify_chroma_knowledge.py
```

（若腳本不在 image 內，請在本機驗證後再上傳。）

## 4. 啟動

在 repo 根目錄（VM 上 `/opt/streamer_toolbox` 或你的 clone 路徑）：

```bash
export GCP_PROJECT_ID=your-project-id
bash deploy/up.sh
```

`up.sh` 會：

1. `fetch_secrets.sh` → 從 Secret Manager 寫入 `/run/secrets/.env`
2. `docker compose -f deploy/docker-compose.gcp.yml up -d --build`

Compose 固定使用 `--stack ingress-chat` 與 `RECORD_MODE=chat`（見 [deploy/docker-compose.gcp.yml](../deploy/docker-compose.gcp.yml)）。

檢查狀態：

```bash
docker compose -f deploy/docker-compose.gcp.yml ps
docker compose -f deploy/docker-compose.gcp.yml logs -f ingress-stack llm-stack
```

### 通過條件

| 項目 | 驗證 |
|------|------|
| 容器 | `rabbitmq`、`ingress-stack`、`llm-stack` 皆 `running` |
| 聊天 | Twitch 輸入 `!ask 測試`，Bot 帳號回覆 |
| 持久化 | `docker compose ... restart` 後 QA memory / Chroma 仍可用 |
| 無 STT | `ingress-stack` log 不應出現 `ingress-twitch-audio` / Whisper 載入訊息 |

## 5. 環境變數對照

Compose 會覆寫下列路徑（見 [deploy/docker-compose.gcp.yml](../deploy/docker-compose.gcp.yml)）：

| 變數 | GCP 值 |
|------|--------|
| `RABBITMQ_URL` | `amqp://guest:guest@rabbitmq:5672/` |
| `STREAM_DB_PATH` | `/data/stream_text.db` |
| `LLM_CHROMA_DIR` | `/data/chroma` |
| `STREAMER_CONFIG_DIR` | `/config` |
| `LLM_KNOWLEDGE_PATH` | `/config/knowledge` |
| `RECORD_MODE` | `chat`（僅記錄聊天，不訂閱 `stt.segment`） |

其餘產品 C 設定見 [deploy/.env.gcp.example](../deploy/.env.gcp.example) 與 [.env.example](../.env.example)。**勿**在 GCP secret 內設定 `STT_*` 或 `TWITCH_STREAMLINK_AUTH_TOKEN`（僅 STT 拉流用）。

可選環境變數（啟動腳本）：

| 變數 | 預設 | 說明 |
|------|------|------|
| `STREAMER_SECRET_NAME` | `streamer-toolbox-env` | Secret Manager 名稱 |
| `STREAMER_ENV_FILE` | `/run/secrets/.env` | 產出的 env 檔路徑 |
| `STREAMER_DATA_DIR` | `/data` | 宿主機資料目錄 |
| `STREAMER_CONFIG_DIR` | `/config` | 宿主機設定目錄 |

## 6. 維運

```bash
# 停止
bash deploy/down.sh

# 本機程序（非 Docker 開發時）
bash scripts/stop_all.sh
bash scripts/list_procs.sh
```

更新版本：

```bash
git pull
bash deploy/up.sh
```

OAuth token 過期：在本機重跑 `first_time_auth.py`，更新 Secret 後 `bash deploy/up.sh`。

## 7. 成本與監控（建議）

- **Compute**：單台 `e2-standard-2` 常駐即可（純文字）；依直播時數評估是否排程開關機。
- **磁碟**：監控 `/data` 用量（SQLite、Chroma、日誌）。
- **日誌**：`docker compose logs` 或安裝 [Ops Agent](https://cloud.google.com/stackdriver/docs/solutions/agents/ops-agent) 轉送 Cloud Logging。
- **Secret**：勿將 `.env` bake 進 Docker image；僅透過 Secret Manager 注入。

## 8. 後續演進（Phase 2）

| 項目 | 說明 |
|------|------|
| `app.workers` | 新增第三個 compose service（L2 **聊天**摘要）；啟用後長期記憶 RAG 才會有內容，見上方 [chat-only 記憶 worker](#chat-only-記憶-worker可選) |
| 雲端 STT | **不建議**；改採 T4 本機 `ingress-local-audio` → 遠端 MQ |
| GKE | 每程序一 Deployment + PVC |
| EventSub Webhook | 需 HTTPS Load Balancer + `ingress-webhook` |
| 實況機 overlay | LocalPC 訂閱遠端 `RABBITMQ_URL`（GCP broker） |

## 相關文件

- [getting-started.md](getting-started.md) — 本機安裝與 OAuth
- [operator-modes.md](operator-modes.md) — AI 問答方案程序表
- [deployment.md](deployment.md) — Pub/Sub 部署邊界與 MQ 規則
- [architecture/control-plane.md § T4](architecture/control-plane.md#t4--hybrid-stt) — 本機 STT + 雲端邏輯
