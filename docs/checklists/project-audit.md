# 專案系統性檢查清單

統一的全專案稽核入口，補上 [pub-sub-writing.md](pub-sub-writing.md)（逐模組）與 [solid.md](../solid.md)（設計準則）之外的「整體健康度」視角。

依風險與頻率分三層：Layer 1 每次 PR 必過、Layer 2 合併／發版前、Layer 3 週期性深度審查。

**圖例：** ✅ 已自動化 · 🔧 腳本輔助 · 👤 人工確認

---

## 一鍵稽核腳本

多數 Layer 1 與 Layer 2 自動項由 [`scripts/audit_project.py`](../../scripts/audit_project.py) 涵蓋：

```powershell
# 本機完整：架構／契約 + ruff + pytest + 營運就緒（.env、RabbitMQ）
uv run python scripts/audit_project.py

# CI 模式：僅架構／契約檢查（ruff、pytest 由專屬 job 執行）
uv run python scripts/audit_project.py --ci

# 加跑跨 process 去重煙霧測試
uv run python scripts/audit_project.py --smoke-dedup
```

通過輸出 `PROJECT_AUDIT_PASS`；任一項失敗輸出 `PROJECT_AUDIT_FAIL` 並列出失敗項與修復提示。

---

## Layer 1 — 自動閘門（每次 PR / push 必過）

對應 CI 三 job：`lint`、`test`、`audit`（見 [.github/workflows/test.yml](../../.github/workflows/test.yml)）。

- [ ] ✅ `ruff` 靜態分析無錯：`uv run ruff check .`
- [ ] ✅ 全 workspace 測試通過：`uv run pytest -q`
- [ ] ✅ 單向依賴：`packages/` 不得 `import app` / `from app`
- [ ] ✅ 命名風險（規則五）：`scripts/naming_audit.py` 三項檢查 — 跨 package 同名 class／函式、app↔package 同名 class（白名單見該模組常數）
- [ ] ✅ `testpaths` 完整：每個有 `tests/` 的 package 都列入根 [pyproject.toml](../../pyproject.toml)
- [ ] ✅ 程序註冊無漂移：`app.main list` 與 [pub-sub-writing.md](pub-sub-writing.md) 速查總表一致
- [ ] ✅ Topic 契約集中：`app/` 內不得散落 topic 字面量（須引用 `events.topics` 常數）
- [ ] ✅ 控制面 builtin 完整：`control` registry 含 `rule-bot` / `llm-bot` / `show-overlay` / `visual-egress`
- [ ] ✅ 控制面 event 已匯出：`events.__init__` 匯出 `config.changed` 等 control-plane events

CI 由三個 job 分工：`lint`（ruff）、`test`（pytest）、`audit`（其餘架構／契約檢查）。本機可跑 `uv run python scripts/audit_project.py`（完整，含 ruff/pytest）或 `--ci`（僅架構／契約，快速）。

---

## Layer 2 — 本機完整稽核（合併前 / 發版前）

涵蓋 Layer 1 全部，外加環境相依與人工確認。

- [ ] 🔧 營運環境就緒：`uv run python scripts/audit_project.py`（含 `.env`、RabbitMQ；重用 [verify_setup.py](../../scripts/verify_setup.py)）
- [ ] 🔧 跨 process 冪等去重：`--smoke-dedup`（或直接跑 [verify_dedup.py](../../scripts/verify_dedup.py)）
- [ ] 🔧 知識庫（如有變更）：[verify_chroma_knowledge.py](../../scripts/verify_chroma_knowledge.py)
- [ ] 🔧 LLM prompt 組裝（如改 sub-llm）：[verify_llm_prompt.py](../../scripts/verify_llm_prompt.py)
- [ ] 👤 受影響 stack 已重啟並確認啟動 log（見 [.cursor/rules/auto-restart-services.mdc](../../.cursor/rules/auto-restart-services.mdc)）
- [ ] 👤 手動 E2E smoke：依 [getting-started.md](../getting-started.md) 第 2 層逐步驗證
- [ ] 👤 commit 訊息符合 `type: emoji [AI] subject`（pre-commit `commit-msg` hook 會擋）

---

## Layer 3 — 週期性深度審查（每季 / 重大重構前）

無法（或不值得）自動化的設計與覆蓋率審查。

### 設計合規

- [ ] 👤 逐模組過 [solid.md](../solid.md) 檢查清單（S / O / L / I / D）
- [ ] 👤 [pub-sub-writing.md](pub-sub-writing.md) 速查總表逐項核對狀態欄（✅ / ⚠️ / 📋）
- [ ] 👤 控制面 Phase 進度對照 [plans/control-plane-phase-01.md](../plans/control-plane-phase-01.md)

### 測試覆蓋薄弱點（已知 baseline，逐步補強）

| 套件 | 現況 | 行動 |
|------|------|------|
| `bus` | `config` + protocol 單元測試 | 已補；RabbitMQ adapter 整合測試仍待評估 |
| `ttvchat-lens` | `reader` 解析／正規化單元測試 | 已補；WebSocket 整合測試仍待評估 |
| `tubechat-lens` | `reader` 正規化／ChatMessage 單元測試 | 已補；pytchat 整合測試仍待評估 |

### 首次稽核 baseline

| 項目 | 現況 | 行動 |
|------|------|------|
| ruff `check .` | 已清理至零（CI `lint` job 綠） | 維持；新違規由 CI 擋下 |
| 殘留除錯插樁 | 已移除（原散落於 `ingress_yt_read`、`tubechat-lens/reader.py`、`sub_llm/*` 等 6 檔的 `_agent_log` / `debug-*.log`） | 完成 |

### 工具鏈未來改善（刻意暫不導入）

- [ ] 👤 評估導入型別檢查（mypy / pyright）
- [ ] 👤 評估導入覆蓋率報告（pytest-cov）

---

## 維護

新增 package、subscriber、publisher 或 topic 時，須同步：

1. 更新 [pub-sub-writing.md](pub-sub-writing.md) 速查總表（否則 `registry_drift` 會失敗）
2. 在 `events.topics` 定義 topic 常數，勿在 `app/` 寫字面量（否則 `topic_magic_strings` 會失敗）
3. 若 package 含 `tests/`，加入根 [pyproject.toml](../../pyproject.toml) 的 `testpaths`（否則 `testpaths_complete` 會失敗）
