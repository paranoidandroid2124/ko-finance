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

_STORE_LOCK = RLock()
_STORE_CACHE: Optional[Dict[str, Dict[str, object]]] = None


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
    watchlist: bool = True
    chat: bool = True

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, object]]) -> "UserLightMemSettings":
        data = payload or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            watchlist=bool(data.get("watchlist", True)),
            chat=bool(data.get("chat", True)),
        )

    def to_dict(self) -> Dict[str, bool]:
        return {
            "enabled": bool(self.enabled),
            "watchlist": bool(self.watchlist),
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


__all__ = [
    "UserLightMemSettings",
    "UserLightMemSettingsRecord",
    "read_user_lightmem_settings",
    "write_user_lightmem_settings",
    "delete_user_lightmem_settings",
]
