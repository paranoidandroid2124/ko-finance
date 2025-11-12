"""Loader for campaign/campaign asset settings."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from core.env import env_str
from core.logging import get_logger
from services.admin_shared import ensure_parent_dir

DEFAULT_CAMPAIGN_SETTINGS_PATH = Path("uploads") / "admin" / "campaign_settings.json"

logger = get_logger(__name__)

_CAMPAIGN_SETTINGS_CACHE: Optional[Dict[str, Any]] = None
_CAMPAIGN_SETTINGS_PATH: Optional[Path] = None

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "starter_promo": {
        "enabled": False,
        "banner": {
            "headline": "Starter 30일 체험으로 워치리스트 자동화를 시작해 보세요",
            "body": "워치리스트 50개 · 알림 룰 10개 · 하루 80회 RAG 질문이 포함됩니다. 기간 안에 해지해도 비용이 청구되지 않아요.",
            "ctaLabel": "Starter 바로 시작",
            "dismissLabel": "지금은 괜찮아요",
        },
        "emails": [],
        "kpi": {"events": [], "sinks": []},
    }
}


def _settings_path() -> Path:
    global _CAMPAIGN_SETTINGS_PATH
    env_path = env_str("CAMPAIGN_SETTINGS_FILE")
    path = Path(env_path) if env_path else DEFAULT_CAMPAIGN_SETTINGS_PATH
    _CAMPAIGN_SETTINGS_PATH = path
    ensure_parent_dir(path, logger)
    return path


def _normalize_banner(payload: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    merged = deepcopy(_DEFAULT_SETTINGS["starter_promo"]["banner"])
    if not isinstance(payload, Mapping):
        return merged
    for key in merged:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()
    return merged


def _normalize_emails(payload: Optional[Any]) -> list[Dict[str, Any]]:
    emails: list[Dict[str, Any]] = []
    if not isinstance(payload, list):
        return emails
    for entry in payload:
        if not isinstance(entry, Mapping):
            continue
        template_id = str(entry.get("id") or "").strip()
        subject = str(entry.get("subject") or "").strip()
        body_template = str(entry.get("bodyTemplate") or "").strip()
        if not (template_id and subject and body_template):
            continue
        preview = str(entry.get("preview") or "").strip() or None
        emails.append(
            {
                "id": template_id,
                "subject": subject,
                "preview": preview,
                "bodyTemplate": body_template,
            }
        )
    return emails


def _normalize_kpi(payload: Optional[Mapping[str, Any]]) -> Dict[str, list[str]]:
    if not isinstance(payload, Mapping):
        return {"events": [], "sinks": []}
    events = []
    for item in payload.get("events") or []:
        text = str(item or "").strip()
        if text:
            events.append(text)
    sinks = []
    for item in payload.get("sinks") or []:
        text = str(item or "").strip()
        if text:
            sinks.append(text)
    return {"events": events, "sinks": sinks}


def _merge_settings(raw: Any) -> Dict[str, Any]:
    merged = deepcopy(_DEFAULT_SETTINGS)
    if not isinstance(raw, Mapping):
        return merged

    starter_raw = raw.get("starter_promo")
    if isinstance(starter_raw, Mapping):
        target = merged["starter_promo"]
        target["enabled"] = bool(starter_raw.get("enabled", target["enabled"]))
        target["banner"] = _normalize_banner(starter_raw.get("banner"))
        target["emails"] = _normalize_emails(starter_raw.get("emails"))
        target["kpi"] = _normalize_kpi(starter_raw.get("kpi"))
    return merged


def load_campaign_settings(*, reload: bool = False) -> Dict[str, Any]:
    """Load campaign settings from disk."""

    global _CAMPAIGN_SETTINGS_CACHE
    if _CAMPAIGN_SETTINGS_CACHE is not None and not reload:
        return deepcopy(_CAMPAIGN_SETTINGS_CACHE)

    path = _settings_path()
    if not path.exists():
        logger.warning("Campaign settings file missing at %s; using defaults.", path)
        payload = deepcopy(_DEFAULT_SETTINGS)
    else:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse campaign settings: %s", exc)
            payload = deepcopy(_DEFAULT_SETTINGS)
        else:
            payload = _merge_settings(raw)

    _CAMPAIGN_SETTINGS_CACHE = deepcopy(payload)
    return deepcopy(payload)


def clear_campaign_settings_cache() -> None:
    """Reset cached settings (used by tests/admin tooling)."""

    global _CAMPAIGN_SETTINGS_CACHE
    _CAMPAIGN_SETTINGS_CACHE = None


__all__ = ["load_campaign_settings", "clear_campaign_settings_cache"]
