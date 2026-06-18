# stt-core

STT 共用核心：`SttConfig`、`TranscriptSegment`、模型生命週期、`StreamingSTTWorker`（PCM 串流）、`build_stt_segment_event` 等。

## Canonical import

新程式碼與測試**一律**從此套件匯入：

```python
from stt_core import (
    SttConfig,
    TranscriptSegment,
    StreamingSTTWorker,
    build_stt_segment_event,
)
```

離線去噪（voice-clone 等）：

```python
from stt_core.denoise import suppress_noise_for_stt
```

## 日落條款（Sunset Date）

| 項目 | 日期 |
|------|------|
| **Sunset Date** | **2026-06-18** |
| **移除內容** | 下列 deprecated re-export shim（不再提供向後相容別名） |

已移除的 shim 路徑（請勿再 import）：

| 原 shim 路徑 | 改用 |
|-------------|------|
| `ingress_twitch_audio.config` | `from stt_core import SttConfig` |
| `ingress_twitch_audio.segment` | `from stt_core import TranscriptSegment, build_stt_segment_event` |
| `ingress_twitch_audio.stt_worker` | `from stt_core import StreamingSTTWorker` |
| `voice_clone.stt.config` | `from stt_core import SttConfig` |
| `voice_clone.stt.segment` | `from stt_core import TranscriptSegment` |
| `voice_clone.stt.denoise` | `from stt_core.denoise import ...` |

`voice_clone.stt.worker.OfflineSTTWorker` 仍為 voice-clone 專用離線實作，非 shim。

## 消費者

- `ingress-twitch-audio`、`ingress-local-audio`（app publishers）
- `voice-clone`（`--stt` 離線轉寫）
- `scripts/benchmark/stt_params.py` 等 benchmark 腳本
