# scripts 索引

開發、稽核、營運與部署輔助腳本一覽。依用途分類；實際檔案目前平放於 `scripts/`，
僅 `eval/`（評測案例）與 `benchmark/`（一次性調參）獨立成子目錄。

## 稽核 / pre-commit（CI 與提交閘門）

| 腳本 | 用途 |
|------|------|
| `audit_project.py` | 全專案系統性稽核（架構／契約／衛生）；CI 以 `--ci` 執行 |
| `pre_commit_block_runtime.py` | pre-commit：攔截 runtime 資料、secret、根目錄 `debug-*` |
| `pre_commit_forbidden_strings.py` | pre-commit：攔截已停用的舊式 commit 前綴 |
| `pre_commit_commit_msg.py` | pre-commit：強制 `type: emoji [AI] subject` 格式 |

## 營運（啟停與設定 bootstrap）

| 腳本 | 用途 |
|------|------|
| `stop_all.ps1` / `stop_all.sh` | 停止所有 stack 並清除 PID 鎖 |
| `list_procs.ps1` / `list_procs.sh` | 列出執行中程序 |
| `setup_knowledge.ps1` | 複製知識庫至 `data/knowledge/` |
| `setup_user_config.ps1` | 外部設定目錄（`STREAMER_CONFIG_DIR`）bootstrap |

## 驗證（環境就緒與煙霧測試）

| 腳本 | 用途 |
|------|------|
| `verify_setup.py` / `verify_setup.ps1` | 環境就緒檢查（`.env`、RabbitMQ） |
| `verify_dedup.py` | 跨 process 冪等去重 smoke test |
| `verify_chroma_knowledge.py` | Chroma 知識庫驗證 |
| `verify_llm_prompt.py` | LLM prompt 組裝驗證（固定三題煙霧測試） |
| `ask_inspect.py` | !ask 乾跑：組裝 prompt 並分析記憶／RAG，不呼叫 LLM |
| `first_time_auth.py` | Twitch OAuth 首次授權 |
| `probe_eventsub.py` | EventSub 訂閱探測 |
| `show_summaries.py` | `app.memory_view` 薄包裝（瀏覽 L2 摘要） |

## 評測（`eval/`）

| 腳本 | 用途 |
|------|------|
| `eval_memory_retrieval.py` | 記憶 recall@K 評測；可接 CI `--min-recall` |
| `ask_inspect.py` | !ask 乾跑 prompt 品質檢視；可接 CI `--min-pass-rate` |
| `eval/memory_retrieval_cases.json` | 評測案例 |
| `eval/ask_inspect_cases.json` | ask 乾跑案例（含 expect_layers） |

## Benchmark / 一次性分析（`benchmark/`，不納入 CI）

開發用調參工具，依賴本機音檔，輸出寫入 `logs/`。皆需 `--audio-dir` 指定音檔目錄。

| 腳本 | 用途 |
|------|------|
| `benchmark/stt_params.py` | ingress STT preset CER 評估 |
| `benchmark/whisper_decode.py` | Whisper 解碼參數 OAT 掃描 |
| `benchmark/analyze_aji_filter.py` | 分析檔名 ground truth 被 STT filter 擋下的原因 |
