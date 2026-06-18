# config/ — 設定範本（Tier 3）

此目錄是**版控內的設定範本與預設值**，不是營運設定本身。完整的三層設定故事請見
[`docs/configuration.md`](../docs/configuration.md)。

## 修改營運設定

請勿直接編輯 production 設定於此目錄；改用外部設定目錄（`STREAMER_CONFIG_DIR`）：

```powershell
uv run python -m streamer_config bootstrap
```

`bootstrap` 會將下列範本複製到 `STREAMER_CONFIG_DIR`（預設 `~/streamer-config`），
僅複製不存在的檔案，不會覆蓋既有設定：

| 範本來源 | 目標檔名 |
|---|---|
| `config/examples/bot_responses.example.json` | `bot_responses.json` |
| `config/examples/redemption_responses.example.json` | `redemption_responses.json` |
| `config/examples/character_brain.example.json` | `character_brain.json` |
| `config/llm_subscriber.json` | `llm_subscriber.json` |
| `config/sub_visual.json` | `sub_visual.json` |
| `config/knowledge/<channel>.md` | `knowledge/<channel>.md` |

各模組透過 `streamer_config.resolve_path()` 解析路徑，優先序為：
**專屬環境變數 > `STREAMER_CONFIG_DIR` > repo `config/` 預設值**，因此本目錄仍是
未設定外部目錄時的後備來源。
