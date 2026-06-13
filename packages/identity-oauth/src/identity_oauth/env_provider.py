from __future__ import annotations

from identity_oauth.multi_account_provider import MultiAccountTokenProvider

# 向後相容：現有呼叫端可繼續使用 EnvTokenProvider 名稱。
EnvTokenProvider = MultiAccountTokenProvider
