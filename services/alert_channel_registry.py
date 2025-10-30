"""Shared alert channel validation registry for alerts."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
URL_PATTERN = r"^https?://[^\s]+$"
PAGERDUTY_PATTERN = r"^[a-z0-9]{16,}$"

_REGEX_CACHE: Dict[Tuple[str, str], re.Pattern[str]] = {}


def _compile_regex(pattern: str, flags: str = "") -> re.Pattern[str]:
    key = (pattern, flags or "")
    if key in _REGEX_CACHE:
        return _REGEX_CACHE[key]
    flag_value = 0
    if flags:
        for flag in flags:
            if flag == "i":
                flag_value |= re.IGNORECASE
    compiled = re.compile(pattern, flag_value)
    _REGEX_CACHE[key] = compiled
    return compiled


# Channel validation registry definition. Each rule uses shared schema so it can be serialized to clients.
CHANNEL_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "email": {
        "requiresTarget": True,
        "targetRules": [
            {"type": "required", "message": "수신자를 한 명 이상 입력해주세요."},
            {
                "type": "regex",
                "pattern": EMAIL_PATTERN,
                "message": "유효하지 않은 이메일 주소가 있어요: {invalid}",
                "collectInvalid": True,
            },
        ],
        "metadataRules": {
            "subject_template": [
                {
                    "type": "min_length",
                    "value": 3,
                    "message": "제목 템플릿은 3자 이상 입력해주세요.",
                    "optional": True,
                }
            ],
            "reply_to": [
                {
                    "type": "regex",
                    "pattern": EMAIL_PATTERN,
                    "message": "Reply-To 주소가 올바르지 않아요.",
                    "collectInvalid": True,
                    "optional": True,
                }
            ],
        },
    },
    "telegram": {
        "requiresTarget": False,
        "targetRules": [],
        "metadataRules": {},
    },
    "slack": {
        "requiresTarget": True,
        "targetRules": [
            {"type": "required", "message": "수신자를 한 명 이상 입력해주세요."},
            {
                "type": "regex",
                "pattern": URL_PATTERN,
                "flags": "i",
                "message": "유효한 URL을 입력해주세요.",
                "collectInvalid": False,
            },
        ],
        "metadataRules": {},
    },
    "webhook": {
        "requiresTarget": True,
        "targetRules": [
            {"type": "required", "message": "수신자를 한 명 이상 입력해주세요."},
            {
                "type": "regex",
                "pattern": URL_PATTERN,
                "flags": "i",
                "message": "유효한 URL을 입력해주세요.",
                "collectInvalid": False,
            },
        ],
        "metadataRules": {},
    },
    "pagerduty": {
        "requiresTarget": True,
        "targetRules": [
            {"type": "required", "message": "수신자를 한 명 이상 입력해주세요."},
            {
                "type": "regex",
                "pattern": PAGERDUTY_PATTERN,
                "flags": "i",
                "message": "PagerDuty Routing Key는 16자 이상의 영숫자로 입력해주세요.",
                "collectInvalid": False,
            },
        ],
        "metadataRules": {
            "severity": [
                {
                    "type": "enum",
                    "values": ["info", "warning", "error", "critical"],
                    "message": "지원하지 않는 Severity 값입니다.",
                    "optional": True,
                }
            ]
        },
    },
}


def get_channel_definition(channel_type: str) -> Optional[Dict[str, Any]]:
    return CHANNEL_DEFINITIONS.get(channel_type)


def list_channel_definitions(allowed: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    if allowed is None:
        selected = CHANNEL_DEFINITIONS.items()
    else:
        allowed_set = {item.lower() for item in allowed}
        selected = [(key, CHANNEL_DEFINITIONS[key]) for key in CHANNEL_DEFINITIONS if key in allowed_set]
    return [
        {
            "type": channel_type,
            "requiresTarget": definition["requiresTarget"],
            "targetRules": definition.get("targetRules", []),
            "metadataRules": definition.get("metadataRules", {}),
        }
        for channel_type, definition in selected
    ]


def _format_message(message: str, invalid_items: Sequence[str]) -> str:
    if "{invalid}" in message:
        return message.replace("{invalid}", ", ".join(invalid_items))
    return message


def _apply_target_rules(
    channel_type: str,
    targets: Sequence[str],
    rules: Sequence[Mapping[str, Any]],
) -> None:
    for rule in rules:
        rule_type = str(rule.get("type", "")).lower()
        message = str(rule.get("message") or "유효하지 않은 입력입니다.")
        if rule_type == "required":
            if not targets:
                raise ValueError(message)
            continue
        if not targets:
            continue
        if rule_type == "regex":
            pattern_value = str(rule.get("pattern") or "")
            if not pattern_value:
                continue
            flags_value = str(rule.get("flags") or "")
            compiled = _compile_regex(pattern_value, flags_value)
            invalid = [target for target in targets if not compiled.match(target)]
            if invalid:
                formatted = _format_message(message, invalid if rule.get("collectInvalid") else invalid[:1])
                raise ValueError(formatted)
        elif rule_type == "min_length":
            min_length = int(rule.get("value") or 0)
            invalid = [target for target in targets if len(target.strip()) < min_length]
            if invalid:
                formatted = _format_message(message, invalid if rule.get("collectInvalid") else invalid[:1])
                raise ValueError(formatted)
        elif rule_type == "enum":
            allowed_values = {str(item) for item in rule.get("values") or []}
            invalid = [target for target in targets if target not in allowed_values]
            if invalid:
                formatted = _format_message(message, invalid if rule.get("collectInvalid") else invalid[:1])
                raise ValueError(formatted)


def _normalize_metadata_entry(value: Any) -> Any:
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed if trimmed else ""
    return value


def _apply_metadata_rules(
    metadata: MutableMapping[str, Any],
    definition_rules: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    for key, rules in definition_rules.items():
        raw_value = metadata.get(key)
        normalized_value = _normalize_metadata_entry(raw_value)
        is_empty = normalized_value in (None, "", [])
        for rule in rules:
            rule_type = str(rule.get("type", "")).lower()
            message = str(rule.get("message") or "유효하지 않은 입력입니다.")
            optional = bool(rule.get("optional", False))
            if rule_type == "required":
                if is_empty:
                    raise ValueError(message)
                continue
            if is_empty and optional:
                break
            if rule_type == "min_length":
                min_length = int(rule.get("value") or 0)
                if not isinstance(normalized_value, str) or len(normalized_value) < min_length:
                    raise ValueError(message)
            elif rule_type == "regex":
                pattern_value = str(rule.get("pattern") or "")
                if not pattern_value:
                    continue
                flags_value = str(rule.get("flags") or "")
                compiled = _compile_regex(pattern_value, flags_value)
                if not isinstance(normalized_value, str):
                    raise ValueError(message)
                if not compiled.match(normalized_value):
                    raise ValueError(message.replace("{invalid}", normalized_value))
            elif rule_type == "enum":
                allowed_values = {str(item) for item in rule.get("values") or []}
                if str(normalized_value) not in allowed_values:
                    raise ValueError(message)
        if isinstance(normalized_value, str):
            metadata[key] = normalized_value


def validate_channel_payload(
    channel_type: str,
    targets: Sequence[str],
    metadata: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Validate and normalize the payload for a specific channel."""
    definition = get_channel_definition(channel_type)
    if definition is None:
        raise ValueError(f"{channel_type} 채널은 아직 지원되지 않아요.")
    metadata_copy: Dict[str, Any] = {}
    if metadata and isinstance(metadata, Mapping):
        metadata_copy.update({key: _normalize_metadata_entry(value) for key, value in metadata.items()})
    _apply_target_rules(channel_type, targets, definition.get("targetRules", []))
    _apply_metadata_rules(metadata_copy, definition.get("metadataRules", {}))
    sanitized_metadata = {key: value for key, value in metadata_copy.items() if value not in ("", None)}
    return sanitized_metadata

