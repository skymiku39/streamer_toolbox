# voice-clone

離線語音克隆：提供樣本音檔即可合成輸出，基於 [OmniVoice](https://github.com/k2-fsa/OmniVoice)（fp16、較省 VRAM）。

本套件為 **streamer_toolbox monorepo 的可選 workspace 成員**，可獨立運作，**不**依賴 RabbitMQ 或 `streamer-app`。

## 需求

- Python 3.11+（封裝層）
- Python 3.10+、PyTorch 2.4+、NVIDIA GPU（推理環境）
- [uv](https://github.com/astral-sh/uv)

## 安裝

在 monorepo 根目錄：

```powershell
cd D:\github\streamer_toolbox

git submodule update --init packages/voice-clone/vendor/OmniVoice

# 可選 dependency group（不強制所有開發者安裝）
uv sync --group dev --group voice-clone

# 複製設定（根 .env 或 package 本地 .env 擇一）
copy packages\voice-clone\.env.example packages\voice-clone\.env
# 或在根 .env 設定 VOICE_CLONE_*（見根 .env.example）

# OmniVoice 推理環境（需網路 + CUDA，一次性）
powershell -NoProfile -File packages\voice-clone\scripts\setup_omnivoice.ps1

# 預下載模型（需網路；下載時需暫時關閉 VOICE_CLONE_OFFLINE）
powershell -NoProfile -File packages\voice-clone\scripts\fetch_models.ps1
```

也可在 package 目錄內操作：

```powershell
cd packages\voice-clone
copy .env.example .env
powershell -NoProfile -File scripts\setup_omnivoice.ps1
```

## 使用

完整參數說明見 **[docs/omnivoice-options.md](docs/omnivoice-options.md)**。

樣本預設會**降噪 + 修剪頭尾靜音**（封裝層前處理）。有配對 `text/001.txt` 時不必手動填 `--sample-text`；未提供時 OmniVoice 會自動轉寫參考音訊。

```powershell
# 在 monorepo 根目錄
uv run voice-clone path\to\sample.wav `
  --text "今天天氣很好，我們一起來開直播吧。" `
  --out output.wav

# 較快推理（預設 num_step=16；32 品質較好但較慢）
uv run voice-clone path\to\sample.wav `
  --num-step 16 `
  --text "今天天氣很好，我們一起來開直播吧。" `
  --out output.wav

# 可選 STT 轉寫參考音（需 uv sync --group voice-clone --extra stt）
uv run voice-clone path\to\sample.wav --stt --text "..." --out output.wav

# Gradio 網頁版
powershell -NoProfile -File packages\voice-clone\scripts\start_demo.ps1
# 瀏覽器開 http://localhost:8001
```

## 專案結構

```
packages/voice-clone/
├── vendor/OmniVoice/       # git submodule（推理引擎，獨立 .venv）
├── src/voice_clone/        # clone CLI 封裝
├── scripts/                # setup_omnivoice.ps1、fetch_models.ps1、start_demo.ps1
├── docs/                   # omnivoice-options.md（參數參考）
└── tests/
```

## 設定

環境變數優先順序：程序環境 > 工作目錄 `.env` > `packages/voice-clone/.env`（由 `VOICE_CLONE_ROOT` 解析）。

| 變數 | 預設 | 用途 |
|------|------|------|
| `VOICE_CLONE_ROOT` | package 根 | 路徑解析基準 |
| `OMNIVOICE_ROOT` | `./vendor/OmniVoice` | OmniVoice submodule |
| `VOICE_CLONE_MODEL` | `k2-fsa/OmniVoice` | HF 模型 ID |
| `VOICE_CLONE_OFFLINE` | `1` | 強制離線推理 |

詳見 [.env.example](.env.example) 與根目錄 `.env.example` 的 `VOICE_CLONE_*` 區塊。

## 測試

```powershell
# monorepo 根目錄
uv run pytest packages/voice-clone/tests -q

# 或 package 內
cd packages/voice-clone
uv run pytest tests -q
```

## 與直播 stack 的關係

本階段 **不** 接入 `sub-character-voice` 或 RabbitMQ。後續可透過 `packages/tts` 的 `VoiceSynthesizer` 適配整合。

## 授權

- 本專案封裝層：MIT
- OmniVoice：Apache-2.0
