"""Persistence layer for admin-managed UI & UX settings."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.logging import get_logger
from services.admin_audit import append_audit_log
from services.admin_shared import (
    ADMIN_BASE_DIR,
    ensure_parent_dir,
    now_iso,
)

logger = get_logger(__name__)

_ADMIN_DIR = ADMIN_BASE_DIR
_UI_SETTINGS_PATH = _ADMIN_DIR / "ui_settings.json"

_DEFAULT_UI_SETTINGS: Dict[str, Any] = {
    "theme": {
        "primaryColor": "#1F6FEB",
        "accentColor": "#22C55E",
    },
    "defaults": {
        "dateRange": "1M",
        "landingView": "overview",
    },
    "copy": {
        "welcomeHeadline": "??? ?? ??? ?? Nuvien???.",
        "welcomeSubcopy": "???? ??? ??, ??? ????? ??? ????.",
        "quickCta": "?? ?? ????",
    },
    "banner": {
        "enabled": False,
        "message": "",
        "linkLabel": "",
        "linkUrl": "",
    },
    "updatedAt": None,
    "updatedBy": None,
    "note": None,
}

_DATE_RANGE_CHOICES = {"1D", "1W", "1M", "3M", "6M", "1Y"}
_LANDING_VIEW_CHOICES = {"overview", "alerts", "evidence", "operations"}
_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
def _load_raw() -> Dict[str, Any]:
    if _UI_SETTINGS_PATH.exists():
        try:
            payload = json.loads(_UI_SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError as exc:  # pragma: no cover
            logger.warning("Failed to parse UI settings store: %s", exc)
    return dict(_DEFAULT_UI_SETTINGS)


def load_ui_settings() -> Dict[str, Any]:
    """Return the current UI settings snapshot, falling back to defaults."""
    return _load_raw()


def _save_ui_settings(settings: Dict[str, Any]) -> None:
    ensure_parent_dir(_UI_SETTINGS_PATH, logger)
    try:
        _UI_SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to persist UI settings: {exc}") from exc


def _sanitize_color(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a hex string.")
    text = value.strip()
    if not _COLOR_PATTERN.match(text):
        raise ValueError(f"{field} must be a valid hex color (e.g. #1F6FEB).")
    return text.upper()


def _sanitize_optional_url(value: Any) -> str:
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise ValueError("linkUrl must be a string.")
    text = value.strip()
    if text and not text.startswith(("http://", "https://")):
        raise ValueError("linkUrl must start with http:// ?? https://")
    return text


def _sanitize_text(value: Any, *, field: str, max_length: int = 300) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    text = value.strip()
    if len(text) > max_length:
        raise ValueError(f"{field} is too long (>{max_length} characters).")
    return text


def _merge_defaults(existing: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = {
        "theme": dict(existing.get("theme", {})),
        "defaults": dict(existing.get("defaults", {})),
        "copy": dict(existing.get("copy", {})),
        "banner": dict(existing.get("banner", {})),
    }
    for section in ("theme", "defaults", "copy", "banner"):
        if section in updates and isinstance(updates[section], dict):
            merged[section].update({key: value for key, value in updates[section].items()})
    return merged


def update_ui_settings(*, settings: Dict[str, Any], actor: str, note: Optional[str]) -> Dict[str, Any]:
    """Validate and persist UI settings, returning the stored snapshot."""
    if not actor or not isinstance(actor, str):
        raise ValueError("actor is required.")

    current = _load_raw()
    merged = _merge_defaults(current, settings)

    theme = merged.get("theme", {})
    defaults = merged.get("defaults", {})
    copy_block = merged.get("copy", {})
    banner = merged.get("banner", {})

    sanitized_theme = {
        "primaryColor": _sanitize_color(theme.get("primaryColor", _DEFAULT_UI_SETTINGS["theme"]["primaryColor"]), field="primaryColor"),
        "accentColor": _sanitize_color(theme.get("accentColor", _DEFAULT_UI_SETTINGS["theme"]["accentColor"]), field="accentColor"),
    }

    date_range = str(defaults.get("dateRange", _DEFAULT_UI_SETTINGS["defaults"]["dateRange"])).upper()
    if date_range not in _DATE_RANGE_CHOICES:
        raise ValueError("dateRange must be one of " + ", ".join(sorted(_DATE_RANGE_CHOICES)))

    landing_view = str(defaults.get("landingView", _DEFAULT_UI_SETTINGS["defaults"]["landingView"]))
    if landing_view not in _LANDING_VIEW_CHOICES:
        raise ValueError("landingView must be one of " + ", ".join(sorted(_LANDING_VIEW_CHOICES)))

    sanitized_defaults = {
        "dateRange": date_range,
        "landingView": landing_view,
    }

    sanitized_copy = {
        "welcomeHeadline": _sanitize_text(copy_block.get("welcomeHeadline"), field="welcomeHeadline", max_length=200),
        "welcomeSubcopy": _sanitize_text(copy_block.get("welcomeSubcopy"), field="welcomeSubcopy", max_length=400),
        "quickCta": _sanitize_text(copy_block.get("quickCta"), field="quickCta", max_length=120),
    }

    banner_enabled = bool(banner.get("enabled", _DEFAULT_UI_SETTINGS["banner"]["enabled"]))
    sanitized_banner = {
        "enabled": banner_enabled,
        "message": _sanitize_text(banner.get("message"), field="banner.message", max_length=240),
        "linkLabel": _sanitize_text(banner.get("linkLabel"), field="banner.linkLabel", max_length=80),
        "linkUrl": _sanitize_optional_url(banner.get("linkUrl")),
    }
    if sanitized_banner["enabled"] and not sanitized_banner["message"]:
        raise ValueError("???? ???? ?? ??? ????.")

    sanitized_note = _sanitize_text(note, field="note", max_length=300) if note else None

    record: Dict[str, Any] = {
        "theme": sanitized_theme,
        "defaults": sanitized_defaults,
        "copy": sanitized_copy,
        "banner": sanitized_banner,
        "updatedAt": now_iso(),
        "updatedBy": actor.strip(),
        "note": sanitized_note,
    }

    _save_ui_settings(record)
    append_audit_log(
        filename="ui_audit.jsonl",
        actor=actor.strip(),
        action="ui_settings_update",
        payload={
            "note": sanitized_note,
            "dateRange": sanitized_defaults["dateRange"],
            "landingView": sanitized_defaults["landingView"],
            "bannerEnabled": sanitized_banner["enabled"],
        },
    )
    return record


__all__ = ["load_ui_settings", "update_ui_settings"]
