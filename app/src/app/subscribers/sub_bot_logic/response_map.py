"""BOT 回應模板（對照 twitch_api utils/bot_responses.py）。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
KEYWORD_MATCH_MODES = frozenset({"contains", "exact"})

ROLE_ORDER: list[str] = ["viewer", "subscriber", "vip", "mod", "broadcaster", "owner"]
ROLE_LEVELS: dict[str, int] = {role: idx for idx, role in enumerate(ROLE_ORDER)}

DEFAULTS: dict[str, dict[str, str]] = {
    "event": {
        "follow": "🎉 感謝 {follower_name} 追隨！",
        "raid": "⚔️ 歡迎 {raider_name} 帶著 {viewer_count} 位觀眾 Raid！",
        "subscribe": "💜 感謝 {subscriber_name} 訂閱 {tier}！{gift_suffix}",
        "subscription_gift": "🎁 感謝 {gifter_name} 贈送 {total} 份 {tier} 訂閱！",
        "subscription_message": "💎 感謝 {subscriber_name} 已訂閱 {months}（{tier}）！",
        "bits": "💎 {user_name} 使用了 {bits} Bits（{type}）{text}",
        "first_chat": "🎉 恭喜 {user} 成為今天第一位發言的觀眾！成功搶到頭香啦！",
    },
    "moderation": {
        "message_delete": "🗑️ {target_user} 的訊息已被刪除",
        "ban": "🔨 {moderator} 對 {banned_user} 執行{action}{reason_suffix}",
        "unban": "✅ {moderator} 解除了 {unbanned_user} 的封鎖",
        "automod_hold": "🤖 AutoMod 攔截了 {user_name} 的訊息：{text}",
        "automod_update": "🤖 {moderator} 已 {status} AutoMod 攔截訊息",
    },
    "system": {
        "poll_begin": "📊 投票開始：{title}（選項：{choices}）",
        "poll_end": "📊 投票結束：{title}（{status}）",
        "prediction_begin": "🔮 預測開始：{title}（{outcomes}）",
        "prediction_lock": "🔮 預測已鎖定：{title}",
        "prediction_end": "🔮 預測結束：{title}（{status}）",
        "hype_train_begin": "🚂 Hype Train 啟動！等級 {level}，累計 {total} 點",
        "hype_train_end": "🚂 Hype Train 結束！最終等級 {level}，累計 {total} 點",
    },
    "command": {
        "ping": "🏓 Pong! Bot 運行中，{author}！",
        "hello": "👋 你好，{author}！歡迎來到 {channel} 的頻道！",
        "info": "🤖 我是 {identity}，一個 Twitch 聊天機器人！使用 !commands 查看可用指令。",
        "echo": "💬 {message}",
        "uptime": "⏱️ Bot 正常運行中！",
        "announce": "📢 公告：{message}",
    },
}

DEFAULT_COMMAND_PERMISSIONS: dict[str, dict[str, Any]] = {
    "commands": {"enabled": True, "min_role": "viewer"},
    "ping": {"enabled": True, "min_role": "viewer"},
    "hello": {"enabled": True, "min_role": "viewer"},
    "info": {"enabled": True, "min_role": "viewer"},
    "echo": {"enabled": True, "min_role": "subscriber"},
    "uptime": {"enabled": True, "min_role": "viewer"},
    "announce": {"enabled": True, "min_role": "mod"},
}

_MODERATION_KEYS = frozenset(DEFAULTS["moderation"].keys())


def _normalize_role(role: str) -> str:
    candidate = str(role or "viewer").strip().lower()
    return candidate if candidate in ROLE_LEVELS else "viewer"


def _normalize_command_key(key: str) -> str:
    return str(key or "").strip().lstrip("!").lower()


class BotResponseMap:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._templates: dict[str, dict[str, str]] = {
            category: dict(values) for category, values in DEFAULTS.items()
        }
        self._command_permissions: dict[str, dict[str, Any]] = {}
        self._keyword_rules: list[dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        try:
            raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
        except FileNotFoundError:
            raw = {}
        except Exception as exc:
            logger.error("載入 BOT 回應模板失敗：%s", exc)
            raw = {}

        try:
            schema_version = int(raw.get("schema_version", 1) or 1)
        except (TypeError, ValueError):
            schema_version = 1
        payload = raw if schema_version >= SCHEMA_VERSION else self._migrate_v1_to_v2(raw)
        self._load_v2_payload(payload)

    def _load_v2_payload(self, payload: dict[str, Any]) -> None:
        self._templates = {}
        for category, defaults in DEFAULTS.items():
            raw_section = payload.get(category, {})
            if category == "command" and isinstance(payload.get("command"), dict):
                raw_section = payload.get("command", {}).get("templates", raw_section)
            self._templates[category] = self._normalize_template_section(raw_section, defaults)

        command_section = payload.get("command", {})
        raw_permissions: Any = {}
        if isinstance(command_section, dict):
            raw_permissions = command_section.get("permissions", {})
        all_command_keys = set(self._templates["command"].keys()) | set(
            DEFAULT_COMMAND_PERMISSIONS.keys()
        )
        self._command_permissions = self._normalize_command_permissions(
            raw_permissions, all_command_keys
        )
        raw_keyword_rules = payload.get("keyword", payload.get("keywords", []))
        self._keyword_rules = self._normalize_keyword_rules(raw_keyword_rules)

    @staticmethod
    def _normalize_template_section(raw_section: Any, defaults: dict[str, str]) -> dict[str, str]:
        normalized = dict(defaults)
        if not isinstance(raw_section, dict):
            return normalized
        for key, value in raw_section.items():
            if str(key).startswith("_"):
                continue
            if isinstance(value, str) and value.strip():
                normalized[str(key)] = value
        return normalized

    @staticmethod
    def _normalize_command_permissions(
        raw_permissions: Any, command_keys: set[str]
    ) -> dict[str, dict[str, Any]]:
        permissions: dict[str, dict[str, Any]] = {}
        for key in sorted(command_keys):
            normalized_key = _normalize_command_key(key)
            if not normalized_key:
                continue
            base = DEFAULT_COMMAND_PERMISSIONS.get(
                normalized_key, {"enabled": True, "min_role": "viewer"}
            )
            permissions[normalized_key] = {
                "enabled": bool(base.get("enabled", True)),
                "min_role": _normalize_role(str(base.get("min_role", "viewer"))),
            }
        if isinstance(raw_permissions, dict):
            for key, value in raw_permissions.items():
                if str(key).startswith("_"):
                    continue
                normalized_key = _normalize_command_key(key)
                if not normalized_key:
                    continue
                data = value if isinstance(value, dict) else {}
                permissions[normalized_key] = {
                    "enabled": bool(
                        data.get(
                            "enabled",
                            permissions.get(normalized_key, {}).get("enabled", True),
                        )
                    ),
                    "min_role": _normalize_role(
                        str(
                            data.get(
                                "min_role",
                                permissions.get(normalized_key, {}).get("min_role", "viewer"),
                            )
                        )
                    ),
                }
        return permissions

    @staticmethod
    def _normalize_keyword_rules(rules: Any) -> list[dict[str, Any]]:
        if not isinstance(rules, list):
            return []
        normalized: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for idx, item in enumerate(rules, start=1):
            if not isinstance(item, dict):
                continue
            trigger = str(item.get("trigger", "")).strip()
            response = str(item.get("response", "")).strip()
            if not trigger or not response:
                continue
            match_mode = str(item.get("match_mode", "contains")).strip().lower()
            if match_mode not in KEYWORD_MATCH_MODES:
                match_mode = "contains"
            try:
                cooldown = int(item.get("cooldown_sec", 0))
            except (TypeError, ValueError):
                cooldown = 0
            rule_id = str(item.get("id", "")).strip() or f"keyword_{idx}"
            if rule_id in seen_ids:
                rule_id = f"{rule_id}_{idx}"
            seen_ids.add(rule_id)
            normalized.append(
                {
                    "id": rule_id,
                    "enabled": bool(item.get("enabled", True)),
                    "trigger": trigger,
                    "response": response,
                    "match_mode": match_mode,
                    "case_sensitive": bool(item.get("case_sensitive", False)),
                    "cooldown_sec": max(0, min(cooldown, 3600)),
                }
            )
        return normalized

    @staticmethod
    def _migrate_v1_to_v2(raw: dict[str, Any]) -> dict[str, Any]:
        events_legacy = raw.get("events", raw.get("event", {}))
        if not isinstance(events_legacy, dict):
            events_legacy = {}
        system_legacy = raw.get("system", {})
        if not isinstance(system_legacy, dict):
            system_legacy = {}
        commands_legacy = raw.get("commands", {})
        if not isinstance(commands_legacy, dict):
            commands_legacy = {}
        command_section = raw.get("command", {})
        if not isinstance(command_section, dict):
            command_section = {}
        command_templates_v2 = command_section.get("templates", {})
        if not isinstance(command_templates_v2, dict):
            command_templates_v2 = {}
        moderation_section = raw.get("moderation", {})
        if not isinstance(moderation_section, dict):
            moderation_section = {}

        moderation_from_legacy: dict[str, Any] = {}
        system_from_legacy: dict[str, Any] = {}
        for key, value in system_legacy.items():
            if key in _MODERATION_KEYS:
                moderation_from_legacy[key] = value
            else:
                system_from_legacy[key] = value

        return {
            "schema_version": SCHEMA_VERSION,
            "event": dict(events_legacy),
            "moderation": {**moderation_from_legacy, **moderation_section},
            "system": dict(system_from_legacy),
            "command": {
                "templates": {**commands_legacy, **command_templates_v2},
                "permissions": command_section.get("permissions", {}),
            },
            "keyword": raw.get("keyword", raw.get("keywords", [])),
        }

    def _resolve_category(self, category: str, key: str = "") -> str:
        aliases = {"events": "event", "commands": "command", "keywords": "keyword"}
        resolved = aliases.get(category, category)
        if resolved == "system" and key in _MODERATION_KEYS:
            return "moderation"
        return resolved if resolved in DEFAULTS else category

    def get(self, category: str, key: str) -> str:
        resolved = self._resolve_category(category, key)
        value = self._templates.get(resolved, {}).get(key, "")
        if value.strip():
            return value
        return DEFAULTS.get(resolved, {}).get(key, "")

    def format(self, category: str, key: str, **kwargs: Any) -> str:
        resolved = self._resolve_category(category, key)
        template = self.get(resolved, key)
        if not template:
            return ""
        try:
            result = template.format(**kwargs)
            if result.strip():
                return result
        except (KeyError, IndexError, ValueError):
            pass
        default = DEFAULTS.get(resolved, {}).get(key, "")
        if not default:
            return ""
        try:
            return default.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return default

    def get_category(self, category: str) -> dict[str, str]:
        resolved = self._resolve_category(category)
        if resolved == "keyword":
            return {}
        merged = dict(DEFAULTS.get(resolved, {}))
        merged.update(self._templates.get(resolved, {}))
        return merged

    def get_command_permission(self, key: str) -> dict[str, Any]:
        command_key = _normalize_command_key(key)
        default = DEFAULT_COMMAND_PERMISSIONS.get(
            command_key, {"enabled": True, "min_role": "viewer"}
        )
        value = self._command_permissions.get(command_key, {})
        return {
            "enabled": bool(value.get("enabled", default.get("enabled", True))),
            "min_role": _normalize_role(
                str(value.get("min_role", default.get("min_role", "viewer")))
            ),
        }

    def can_use_command(self, key: str, role: str) -> bool:
        permission = self.get_command_permission(key)
        if not permission["enabled"]:
            return False
        return ROLE_LEVELS[_normalize_role(role)] >= ROLE_LEVELS[
            _normalize_role(str(permission["min_role"]))
        ]

    def get_keyword_rules(self, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        rules = [dict(item) for item in self._keyword_rules]
        if enabled_only:
            rules = [item for item in rules if bool(item.get("enabled", True))]
        return rules

    @staticmethod
    def format_keyword_response(rule: dict[str, Any], **kwargs: Any) -> str:
        template = str(rule.get("response", "")).strip()
        if not template:
            return ""
        try:
            return template.format(**kwargs).strip()
        except (KeyError, IndexError, ValueError):
            return template
