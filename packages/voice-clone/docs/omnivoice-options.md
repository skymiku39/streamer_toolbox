# OmniVoice 參數與選項參考

本文件整理 [k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice) 在本專案中的可用參數、三種合成模式，以及 `voice-clone` 封裝層與官方 CLI／Web UI 的差異。

---

## 合成模式總覽

| 模式 | 必要輸入 | 說明 |
|------|----------|------|
| **Voice Clone（語音克隆）** | `ref_audio` + 目標 `text` | 複製參考音訊的音色與語氣；`ref_text` 可省略（Whisper 自動轉寫） |
| **Voice Design（語音設計）** | `instruct` + 目標 `text` | 不需參考音訊，用屬性描述生成聲音 |
| **Auto Voice（自動）** | 僅 `text` | 模型隨機選聲音 |

> **注意**：Voice Design 主要針對中英文訓練；克隆模式最穩定。  
> **沒有**「台灣腔／台灣話」等 `instruct` 選項；台式國語需靠**台灣腔參考音訊**克隆。

---

## 1. `voice-clone` CLI（本專案封裝）

```powershell
uv run voice-clone <樣本.wav> --text "要合成的文字" [選項]
```

### 命令列參數

| 參數 | 簡寫 | 預設 | 說明 |
|------|------|------|------|
| `SAMPLE` | — | （必填） | 參考樣本音檔路徑，建議 3–10 秒 |
| `--text` | `-t` | （必填） | 要合成的目標文字 |
| `--out` | `-o` | `output.wav` | 輸出 wav 路徑 |
| `--sample-text` | — | 自動讀取配對 `.txt` | 樣本音檔對應文字；省略時由 OmniVoice Whisper 轉寫 |
| `--stt` | — | `false` | 以本機 faster-whisper 轉寫樣本（需 `uv sync --extra stt`） |
| `--model` | — | `k2-fsa/OmniVoice` | HuggingFace 模型 ID 或本機路徑 |
| `--language` | — | `Chinese` | 合成語言（如 `Chinese`、`English`） |
| `--device` | — | `cuda:0` | 推理裝置 |
| `--num-step` | — | `16` | 擴散步數；16 較快，32 品質較好 |
| `--denoise` / `--no-denoise` | — | 啟用 | 封裝層樣本前處理：降噪 |
| `--trim-silence` / `--no-trim-silence` | — | 啟用 | 封裝層樣本前處理：修剪頭尾靜音 |

### 範例

```powershell
# 基本用法（自動讀取 samples\streamer\text\001.txt）
uv run voice-clone samples\streamer\audio\001.wav `
  --text "今天天氣很好，我們一起來開直播吧！" `
  --out output.wav

# 較高品質
uv run voice-clone samples\streamer\audio\001.wav `
  --num-step 32 `
  --text "今天天氣很好！" `
  --out output_hq.wav

# 關閉封裝層前處理（保留原始樣本細節）
uv run voice-clone samples\streamer\audio\001.wav `
  --no-denoise --no-trim-silence `
  --text "測試原文樣本。" `
  --out output_raw.wav
```

### 封裝層尚未暴露的 OmniVoice 參數

以下需改用 **`omnivoice-infer`** 或 **Web UI**：

- `--instruct`
- `--guidance_scale`、`--speed`、`--duration`
- `--position_temperature`、`--class_temperature`
- `--t_shift`、`--layer_penalty_factor`
- `--denoise`（模型內建，與封裝層樣本降噪不同）
- `--postprocess_output`、`--preprocess_prompt`

---

## 2. `.env` 環境變數

| 變數 | 預設 | 說明 |
|------|------|------|
| `VOICE_CLONE_ROOT` | 專案根目錄 | 專案路徑 |
| `OMNIVOICE_ROOT` | `./vendor/OmniVoice` | OmniVoice submodule 路徑 |
| `VOICE_CLONE_MODEL` | `k2-fsa/OmniVoice` | 預設模型 |
| `VOICE_CLONE_LANGUAGE` | `Chinese` | 預設合成語言 |
| `VOICE_CLONE_DEVICE` | `cuda:0` | 推理裝置 |
| `VOICE_CLONE_NUM_STEP` | `16` | 預設擴散步數 |
| `VOICE_CLONE_SAMPLE_RATE` | `24000` | 輸出取樣率（模型固定 24 kHz） |
| `VOICE_CLONE_OFFLINE` | `1` | 強制離線（下載模型時改 `0`） |
| `HF_HUB_OFFLINE` | `1` | HuggingFace 離線 |
| `TRANSFORMERS_OFFLINE` | `1` | Transformers 離線 |
| `VOICE_CLONE_DENOISE` | `1` | 封裝層樣本降噪（CLI 可覆寫） |
| `VOICE_CLONE_TRIM_SILENCE` | `1` | 封裝層修剪靜音 |
| `VOICE_CLONE_DENOISE_HP_HZ` | `100` | 高通濾波截止頻率（Hz） |
| `VOICE_CLONE_DENOISE_GATE_RATIO` | `0.12` | 頻譜門檻比例；越大降噪越強 |

---

## 3. `omnivoice-infer`（官方單筆推理 CLI）

路徑：`vendor\OmniVoice\.venv\Scripts\omnivoice-infer.exe`

```powershell
cd vendor\OmniVoice
.\.venv\Scripts\omnivoice-infer.exe `
  --model k2-fsa/OmniVoice `
  --text "要合成的文字" `
  --ref_audio ..\..\samples\streamer\audio\001.wav `
  --ref_text "各位觀眾大家好，歡迎來到我的直播間。" `
  --language Chinese `
  --output ..\..\output.wav
```

### 完整參數表

| 參數 | 預設 | 說明 |
|------|------|------|
| `--model` | `k2-fsa/OmniVoice` | 模型路徑或 HF repo id |
| `--text` | （必填） | 合成文字 |
| `--output` | （必填） | 輸出 wav |
| `--ref_audio` | — | 參考音訊（克隆模式） |
| `--ref_text` | — | 參考文字；可省略（Whisper 轉寫） |
| `--instruct` | — | 語音設計屬性字串（見下文） |
| `--language` | 自動 | 語言名稱或代碼（如 `Chinese`、`en`） |
| `--device` | 自動偵測 | 如 `cuda:0` |
| `--num_step` | `32` | 擴散步數 |
| `--guidance_scale` | `2.0` | Classifier-free guidance |
| `--speed` | `1.0` | 語速；>1 較快，<1 較慢 |
| `--duration` | — | 固定輸出秒數（覆寫 speed） |
| `--t_shift` | `0.1` | 噪聲排程時間偏移 |
| `--denoise` | `true` | 模型內建：前置 `<\|denoise\|>` token |
| `--postprocess_output` | `true` | 輸出後處理（去長靜音） |
| `--layer_penalty_factor` | `5.0` | 深層 codebook 懲罰係數 |
| `--position_temperature` | `5.0` | 遮罩位置採樣溫度；0=貪婪 |
| `--class_temperature` | `0.0` | token 採樣溫度；0=貪婪 |

### 三種官方用法

```powershell
# 語音克隆
omnivoice-infer --model k2-fsa/OmniVoice --text "..." --ref_audio ref.wav --ref_text "..." --output out.wav

# 語音設計（無參考音訊）
omnivoice-infer --model k2-fsa/OmniVoice --text "..." --instruct "女，青年，高音调" --output out.wav

# 自動聲音
omnivoice-infer --model k2-fsa/OmniVoice --text "..." --output out.wav
```

---

## 4. `omnivoice-demo`（Gradio 網頁版）

```powershell
cd vendor\OmniVoice
.\.venv\Scripts\omnivoice-demo.exe --model k2-fsa/OmniVoice --device cuda:0 --ip 0.0.0.0 --port 8001
```

瀏覽器：**http://localhost:8001**

### 啟動參數

| 參數 | 預設 | 說明 |
|------|------|------|
| `--model` | `k2-fsa/OmniVoice` | 模型 |
| `--device` | 自動 | 推理裝置 |
| `--ip` | `0.0.0.0` | 綁定 IP |
| `--port` | `7860` | 埠號（本專案建議 `8001`） |
| `--root-path` | — | 反向代理根路徑 |
| `--share` | `false` | 產生 Gradio 公開連結 |
| `--no-asr` | `false` | 跳過 Whisper；無法自動轉寫參考文字 |
| `--asr-model` | `openai/whisper-large-v3-turbo` | ASR 模型 |

### Web UI 可調項目

**Voice Clone 分頁**

| 欄位 | 範圍／預設 | 說明 |
|------|------------|------|
| Text to Synthesize | — | 目標文字 |
| Reference Audio | — | 參考音訊（3–10 秒） |
| Reference Text | 可空 | 參考轉寫；空則 ASR |
| Language | Auto / 600+ 語言 | 建議中文選 Chinese |
| Instruct | 可空 | 與參考音訊搭配（見注意事項） |
| Speed | 0.5–1.5，預設 1.0 | 語速 |
| Duration | 可空 | 固定秒數（覆寫 Speed） |
| Inference Steps | 4–64，預設 32 | 同 `num_step` |
| Denoise | 預設開 | 模型內建降噪 token |
| Guidance Scale | 0–4，預設 2.0 | CFG |
| Preprocess Prompt | 預設開 | 參考音訊去靜音、補標點 |
| Postprocess Output | 預設開 | 輸出去長靜音 |

**Voice Design 分頁**

下拉選單可選：性別、年齡、音調、風格（耳語）、英文口音、中文方言（見下節）。

---

## 5. 生成參數詳解（`model.generate`）

來源：`vendor/OmniVoice/docs/generation-parameters.md`

### 解碼（Decoding）

| 參數 | 預設 | 說明 | 調整建議 |
|------|------|------|----------|
| `num_step` | 32 | 擴散步數 | 16 快；32 品質較好 |
| `denoise` | true | 前置降噪 token | 一般保持開啟 |
| `guidance_scale` | 2.0 | CFG 強度 | 略提高可更貼近提示 |
| `t_shift` | 0.1 | 噪聲排程偏移 | 進階調參 |

### 採樣（Sampling）

| 參數 | 預設 | 說明 | 調整建議 |
|------|------|------|----------|
| `position_temperature` | 5.0 | 位置選擇隨機性 | 提高→節奏變化多（較不穩） |
| `class_temperature` | 0.0 | token 採樣隨機性 | 略提高→細節變化多 |
| `layer_penalty_factor` | 5.0 | 深層懲罰 | 進階調參 |

### 時長與語速

| 參數 | 預設 | 說明 |
|------|------|------|
| `duration` | — | 固定輸出秒數（優先於 speed） |
| `speed` | 1.0 | >1 較快，<1 較慢；0.85–0.95 較有戲劇感 |

### 前後處理

| 參數 | 預設 | 說明 |
|------|------|------|
| `preprocess_prompt` | true | 參考音訊去長靜音、補標點 |
| `postprocess_output` | true | 輸出去長靜音 |

### 長文本分塊

| 參數 | 預設 | 說明 |
|------|------|------|
| `audio_chunk_duration` | 15.0 | 分塊目標長度（秒） |
| `audio_chunk_threshold` | 30.0 | 超過此估計長度才分塊 |

---

## 6. `instruct` 語音設計屬性（完整清單）

每類只能選一項；多類用逗號串接。  
英文用半形 `, `；中文用全形 `，`。

### 性別

| 英文 | 中文 |
|------|------|
| male | 男 |
| female | 女 |

### 年齡

| 英文 | 中文 |
|------|------|
| child | 儿童 |
| teenager | 少年 |
| young adult | 青年 |
| middle-aged | 中年 |
| elderly | 老年 |

### 音調

| 英文 | 中文 |
|------|------|
| very low pitch | 极低音调 |
| low pitch | 低音调 |
| moderate pitch | 中音调 |
| high pitch | 高音调 |
| very high pitch | 极高音调 |

### 風格

| 英文 | 中文 |
|------|------|
| whisper | 耳语 |

### 英文口音（僅英文文本有效）

`american accent`、`british accent`、`australian accent`、`canadian accent`、`indian accent`、`chinese accent`、`korean accent`、`japanese accent`、`portuguese accent`、`russian accent`

### 中文方言（僅中文文本有效）

`河南话`、`陕西话`、`四川话`、`贵州话`、`云南话`、`桂林话`、`济南话`、`石家庄话`、`甘肃话`、`宁夏话`、`青岛话`、`东北话`

### 範例

```
女，青年，高音调
female, young adult, high pitch
male, elderly, low pitch, whisper
```

### 與 `ref_audio` 併用

- **衝突**時：多半跟參考音訊走  
- **一致**時：可提升穩定度（如四川話音檔 + `四川话`）  
- **無效值**（如 `台灣話`）會直接 `ValueError`

---

## 7. 文本進階控制

### 非語言標籤（插入目標文字）

| 標籤 | 效果 |
|------|------|
| `[laughter]` | 笑聲 |
| `[sigh]` | 嘆息 |
| `[confirmation-en]` | 英文確認語氣 |
| `[question-en]` `[question-ah]` `[question-oh]` `[question-ei]` `[question-yi]` | 疑問語氣 |
| `[surprise-ah]` `[surprise-oh]` `[surprise-wa]` `[surprise-yo]` | 驚訝 |
| `[dissatisfaction-hnn]` | 不滿／哼聲 |

範例：

```
[surprise-ah] 哇！今天天氣超好！[laughter] 我們馬上開直播吧！
```

### 發音校正

- **中文**：拼音+聲調，如 `打ZHE2出售`、`嚴重SHE2本`
- **英文**：CMU 音標大寫方括號，如 `[B EY1 S]`、`[B AE1 S]`

### 實用文本技巧

- 標點（！？…）影響停頓與語氣  
- 參考音訊情緒決定克隆語氣（興奮樣本→興奮輸出）  
- 參考音訊與目標文字**同語言**發音最標準  
- 阿拉伯數字建議先正規化成文字

---

## 8. 推薦參數組合

| 場景 | 建議 |
|------|------|
| 日常快速合成 | `num_step=16`，封裝層預設前處理 |
| 較高品質 | `num_step=32` |
| 更有起伏 | 情緒化參考音訊 + 標點 + 非語言標籤 + `num_step=32` |
| 略慢、較有戲劇感 | `speed=0.9`（`omnivoice-infer` 或 Web UI） |
| 更多節奏變化 | `position_temperature=6.0`（可能較不穩定） |
| 台式國語 | 台灣腔參考音訊克隆；**勿**用 `instruct` 填地區 |

---

## 9. 官方文件連結

| 主題 | 路徑 |
|------|------|
| 生成參數 | `vendor/OmniVoice/docs/generation-parameters.md` |
| 語音設計 | `vendor/OmniVoice/docs/voice-design.md` |
| 使用技巧 | `vendor/OmniVoice/docs/tips.md` |
| 支援語言列表 | `vendor/OmniVoice/docs/languages.md` |
| 官方 README | `vendor/OmniVoice/README.md` |

---

## 10. 工具對照速查

| 功能 | voice-clone | omnivoice-infer | Web UI |
|------|:-----------:|:---------------:|:------:|
| 語音克隆 | ✅ | ✅ | ✅ |
| 語音設計 | ❌ | ✅ | ✅ |
| 自動聲音 | ❌ | ✅ | ❌ |
| 樣本前處理（封裝層降噪） | ✅ | ❌ | ❌ |
| 配對 text/ 自動讀取 | ✅ | ❌ | ❌ |
| 完整生成參數 | 部分 | ✅ | 大部分 |
| instruct | ❌ | ✅ | ✅ |
| 非語言標籤 | ✅（寫在 --text） | ✅ | ✅ |
| 離線模式整合 | ✅ | 手動設 env | 手動設 env |
