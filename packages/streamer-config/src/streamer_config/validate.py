"""設定檔驗證（存檔前）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from streamer_config.paths import (
    BOT_RESPONSES_NAME,
    LLM_SUBSCRIBER_NAME,
    REDEMPTION_RESPONSES_NAME,
    SUB_VISUAL_NAME,
    ConfigPaths,
)

KEYWORD_MATCH_MODES = frozenset({"contains", "exact"})
COMMAND_ROLES = frozenset({"viewer", "subscriber", "vip", "mod", "broadcaster", "owner"})


class ValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        message = "; ".join(self.errors) if self.errors else "validation failed"
        super().__init__(message)


def _require_dict(value: Any, field: str, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{field} must be an object")
    return {}


def _validate_bot_responses_payload(payload: dict[str, Any], errors: list[str]) -> None:
    try:
        schema_version = int(payload.get("schema_version", 1) or 1)
    except (TypeError, ValueError):
        errors.append("schema_version must be an integer")
        schema_version = 1

    if schema_version < 1:
        errors.append("schema_version must be >= 1")

    for section in ("event", "moderation", "system"):
        section_value = payload.get(section)
        if section_value is None:
            continue
        section_dict = _require_dict(section_value, section, errors)
        for key, value in section_dict.items():
            if str(key).startswith("_"):
                continue
            if not isinstance(value, str):
                errors.append(f"{section}.{key} must be a string template")

    command_section = payload.get("command", {})
    if command_section is not None and not isinstance(command_section, dict):
        errors.append("command must be an object")
    elif isinstance(command_section, dict):
        templates = command_section.get("templates", command_section)
        templates_dict = _require_dict(templates, "command.templates", errors)
        for key, value in templates_dict.items():
            if str(key).startswith("_"):
                continue
            if not isinstance(value, str):
                errors.append(f"command.templates.{key} must be a string")

        permissions = command_section.get("permissions", {})
        if permissions is not None:
            permissions_dict = _require_dict(permissions, "command.permissions", errors)
            for key, value in permissions_dict.items():
                if str(key).startswith("_"):
                    continue
                perm = _require_dict(value, f"command.permissions.{key}", errors)
                if "min_role" in perm:
                    role = str(perm.get("min_role", "")).strip().lower()
                    if role and role not in COMMAND_ROLES:
                        errors.append(f"command.permissions.{key}.min_role is invalid: {role}")

    keyword_rules = payload.get("keyword", payload.get("keywords", []))
    if keyword_rules is None:
        return
    if not isinstance(keyword_rules, list):
        errors.append("keyword must be an array")
        return

    for idx, item in enumerate(keyword_rules, start=1):
        if not isinstance(item, dict):
            errors.append(f"keyword[{idx}] must be an object")
            continue
        trigger = str(item.get("trigger", "")).strip()
        response = str(item.get("response", "")).strip()
        if not trigger:
            errors.append(f"keyword[{idx}].trigger is required")
        if not response:
            errors.append(f"keyword[{idx}].response is required")
        match_mode = str(item.get("match_mode", "contains")).strip().lower()
        if match_mode not in KEYWORD_MATCH_MODES:
            errors.append(f"keyword[{idx}].match_mode must be contains or exact")


def _validate_redemption_payload(payload: dict[str, Any], errors: list[str]) -> None:
    for key, value in payload.items():
        if str(key).startswith("_"):
            continue
        if not isinstance(value, str):
            errors.append(f"redemption.{key} must be a string template")


def _validate_llm_subscriber_payload(payload: dict[str, Any], errors: list[str]) -> None:
    prefixes = payload.get("trigger_prefixes")
    if prefixes is not None:
        if not isinstance(prefixes, list) or not all(isinstance(item, str) for item in prefixes):
            errors.append("trigger_prefixes must be an array of strings")
        elif not prefixes:
            errors.append("trigger_prefixes must not be empty")

    for numeric_key in ("context_window_minutes", "reply_max_length"):
        if numeric_key not in payload:
            continue
        try:
            int(payload[numeric_key])
        except (TypeError, ValueError):
            errors.append(f"{numeric_key} must be an integer")

    for list_key in ("input_blocklist", "output_blocklist"):
        if list_key not in payload:
            continue
        value = payload[list_key]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{list_key} must be an array of strings")


def _validate_sub_visual_payload(payload: dict[str, Any], errors: list[str]) -> None:
    backend = payload.get("backend")
    if backend is not None and backend not in {"file", "spout2"}:
        errors.append("backend must be file or spout2")

    filter_section = payload.get("filter")
    if filter_section is not None:
        filter_dict = _require_dict(filter_section, "filter", errors)
        if "min_length" in filter_dict:
            try:
                int(filter_dict["min_length"])
            except (TypeError, ValueError):
                errors.append("filter.min_length must be an integer")
        blocked = filter_dict.get("blocked_keywords")
        if blocked is not None and (
            not isinstance(blocked, list) or not all(isinstance(item, str) for item in blocked)
        ):
            errors.append("filter.blocked_keywords must be an array of strings")


def validate_knowledge_filename(filename: str) -> None:
    name = str(filename or "").strip()
    if not name.endswith(".md"):
        raise ValidationError(["knowledge filename must end with .md"])
    if name != Path(name).name or ".." in name:
        raise ValidationError(["knowledge filename must not contain path separators"])


def validate_json_content(name: str, content: str) -> dict[str, Any]:
    errors: list[str] = []
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValidationError([f"{name}: invalid JSON: {exc.msg}"]) from exc

    if not isinstance(payload, dict):
        raise ValidationError([f"{name}: root must be an object"])

    if name == BOT_RESPONSES_NAME:
        _validate_bot_responses_payload(payload, errors)
    elif name == REDEMPTION_RESPONSES_NAME:
        _validate_redemption_payload(payload, errors)
    elif name == LLM_SUBSCRIBER_NAME:
        _validate_llm_subscriber_payload(payload, errors)
    elif name == SUB_VISUAL_NAME:
        _validate_sub_visual_payload(payload, errors)
    else:
        errors.append(f"unsupported config file: {name}")

    if errors:
        raise ValidationError(errors)
    return payload


def validate_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValidationError([f"file not found: {path}"])
    content = path.read_text(encoding="utf-8")
    return validate_json_content(path.name, content)


def validate_all(paths: ConfigPaths) -> list[str]:
    errors: list[str] = []
    checks = [
        paths.bot_responses,
        paths.redemption_responses,
        paths.llm_subscriber,
        paths.sub_visual,
    ]
    for path in checks:
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.extend(exc.errors)
    return errors
