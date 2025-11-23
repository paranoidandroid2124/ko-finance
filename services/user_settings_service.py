"""Disk-backed helpers for per-user LightMem preference settings."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Dict, Optional

from core.logging import get_logger
from services.json_store import read_json_document, write_json_document

logger = get_logger(__name__)

_LIGHTMEM_PATH = Path("uploads") / "user_settings" / "lightmem_preferences.json"
_PROACTIVE_PATH = Path("uploads") / "user_settings" / "proactive_preferences.json"

_STORE_LOCK = RLock()
_STORE_CACHE: Optional[Dict[str, Dict[str, object]]] = None
_PROACTIVE_STORE_CACHE: Optional[Dict[str, Dict[str, object]]] = None


def _load_store() -> Dict[str, Dict[str, object]]:
    global _STORE_CACHE  # pylint: disable=global-statement
    if _STORE_CACHE is not None:
        return _STORE_CACHE

    payload = read_json_document(_LIGHTMEM_PATH, default=dict)
    if isinstance(payload, dict):
        _STORE_CACHE = payload
    else:
        logger.warning("LightMem user settings file is malformed; resetting cache.")
        _STORE_CACHE = {}
    return _STORE_CACHE


def _save_store(store: Dict[str, Dict[str, object]]) -> None:
    global _STORE_CACHE  # pylint: disable=global-statement
    write_json_document(_LIGHTMEM_PATH, store)
    _STORE_CACHE = dict(store)


def _load_proactive_store() -> Dict[str, Dict[str, object]]:
    global _PROACTIVE_STORE_CACHE  # pylint: disable=global-statement
    if _PROACTIVE_STORE_CACHE is not None:
        return _PROACTIVE_STORE_CACHE

    payload = read_json_document(_PROACTIVE_PATH, default=dict)
    if isinstance(payload, dict):
        _PROACTIVE_STORE_CACHE = payload
    else:
        logger.warning("Proactive settings file is malformed; resetting cache.")
        _PROACTIVE_STORE_CACHE = {}
    return _PROACTIVE_STORE_CACHE


def _save_proactive_store(store: Dict[str, Dict[str, object]]) -> None:
    global _PROACTIVE_STORE_CACHE  # pylint: disable=global-statement
    write_json_document(_PROACTIVE_PATH, store)
    _PROACTIVE_STORE_CACHE = dict(store)


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.debug("Invalid LightMem settings timestamp %s", value)
        return None


@dataclass
class UserLightMemSettings:
    """Per-user LightMem opt-in flags."""

    enabled: bool = False
    chat: bool = True

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, object]]) -> "UserLightMemSettings":
        data = payload or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            chat=bool(data.get("chat", True)),
        )

    def to_dict(self) -> Dict[str, bool]:
        return {
            "enabled": bool(self.enabled),
            "chat": bool(self.chat),
        }


@dataclass
class UserLightMemSettingsRecord:
    """Snapshot of stored LightMem settings along with metadata."""

    user_id: uuid.UUID
    updated_at: Optional[datetime]
    updated_by: Optional[str]
    settings: UserLightMemSettings


def read_user_lightmem_settings(user_id: uuid.UUID) -> UserLightMemSettingsRecord:
    """Return stored LightMem settings for ``user_id`` (defaults if missing)."""
    with _STORE_LOCK:
        store = _load_store()
        entry = store.get(str(user_id)) or {}

    settings = UserLightMemSettings.from_dict(entry.get("lightmem"))
    updated_at = _parse_timestamp(entry.get("updatedAt"))
    updated_by = entry.get("updatedBy")
    return UserLightMemSettingsRecord(
        user_id=user_id,
        updated_at=updated_at,
        updated_by=str(updated_by) if updated_by else None,
        settings=settings,
    )


def write_user_lightmem_settings(
    user_id: uuid.UUID,
    *,
    settings: UserLightMemSettings,
    actor: Optional[str] = None,
) -> UserLightMemSettingsRecord:
    """Persist the supplied LightMem settings for ``user_id``."""
    now = datetime.now(timezone.utc)
    entry = {
        "lightmem": settings.to_dict(),
        "updatedAt": now.isoformat(),
        "updatedBy": actor or None,
    }
    with _STORE_LOCK:
        store = dict(_load_store())
        store[str(user_id)] = entry
        _save_store(store)

    return UserLightMemSettingsRecord(
        user_id=user_id,
        updated_at=now,
        updated_by=entry["updatedBy"],
        settings=settings,
    )


def delete_user_lightmem_settings(user_id: uuid.UUID) -> bool:
    """Remove persisted LightMem preferences for ``user_id`` if they exist."""
    with _STORE_LOCK:
        store = dict(_load_store())
        removed = store.pop(str(user_id), None)
        if removed is None:
            return False
        _save_store(store)
        return True


@dataclass
class UserProactiveSettings:
    """Per-user proactive insight preferences."""

    enabled: bool = False
    widget: bool = True
    email_enabled: bool = False
    email_schedule: str = "morning"
    slack_enabled: bool = False
    preferred_tickers: list[str] = None  # optional allow list
    blocked_tickers: list[str] = None
    preferred_sectors: list[str] = None
    blocked_sectors: list[str] = None

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, object]]) -> "UserProactiveSettings":
        data = payload or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            widget=bool(data.get("widget", True)),
            email_enabled=bool(data.get("email_enabled", False)),
            email_schedule=str(data.get("email_schedule") or "morning"),
            slack_enabled=bool(data.get("slack_enabled", False)),
            preferred_tickers=list(data.get("preferred_tickers") or []) if isinstance(data.get("preferred_tickers"), list) else [],
            blocked_tickers=list(data.get("blocked_tickers") or []) if isinstance(data.get("blocked_tickers"), list) else [],
            preferred_sectors=list(data.get("preferred_sectors") or []) if isinstance(data.get("preferred_sectors"), list) else [],
            blocked_sectors=list(data.get("blocked_sectors") or []) if isinstance(data.get("blocked_sectors"), list) else [],
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "enabled": bool(self.enabled),
            "widget": bool(self.widget),
            "email_enabled": bool(self.email_enabled),
            "email_schedule": self.email_schedule or "morning",
            "slack_enabled": bool(self.slack_enabled),
            "preferred_tickers": list(self.preferred_tickers or []),
            "blocked_tickers": list(self.blocked_tickers or []),
            "preferred_sectors": list(self.preferred_sectors or []),
            "blocked_sectors": list(self.blocked_sectors or []),
        }


@dataclass
class UserProactiveSettingsRecord:
    user_id: uuid.UUID
    updated_at: Optional[datetime]
    updated_by: Optional[str]
    settings: UserProactiveSettings


def read_user_proactive_settings(user_id: uuid.UUID) -> UserProactiveSettingsRecord:
    """Return stored proactive notification preferences for ``user_id`` (defaults if missing)."""
    with _STORE_LOCK:
        store = _load_proactive_store()
        entry = store.get(str(user_id)) or {}

    settings = UserProactiveSettings.from_dict(entry.get("proactive"))
    updated_at = _parse_timestamp(entry.get("updatedAt"))
    updated_by = entry.get("updatedBy")
    return UserProactiveSettingsRecord(
        user_id=user_id,
        updated_at=updated_at,
        updated_by=str(updated_by) if updated_by else None,
        settings=settings,
    )


def write_user_proactive_settings(
    user_id: uuid.UUID,
    *,
    settings: UserProactiveSettings,
    actor: Optional[str] = None,
) -> UserProactiveSettingsRecord:
    """Persist proactive settings for ``user_id``."""
    now = datetime.now(timezone.utc)
    entry = {
        "proactive": settings.to_dict(),
        "updatedAt": now.isoformat(),
        "updatedBy": actor or None,
    }
    with _STORE_LOCK:
        store = dict(_load_proactive_store())
        store[str(user_id)] = entry
        _save_proactive_store(store)

    return UserProactiveSettingsRecord(
        user_id=user_id,
        updated_at=now,
        updated_by=entry["updatedBy"],
        settings=settings,
    )


__all__ = [
    "UserLightMemSettings",
    "UserLightMemSettingsRecord",
    "read_user_lightmem_settings",
    "write_user_lightmem_settings",
    "delete_user_lightmem_settings",
    "UserProactiveSettings",
    "UserProactiveSettingsRecord",
    "read_user_proactive_settings",
    "write_user_proactive_settings",
]
