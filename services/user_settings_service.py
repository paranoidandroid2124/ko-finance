"""Disk-backed helpers for per-user LightMem preference settings."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Dict, Optional

from core.logging import get_logger

logger = get_logger(__name__)

_SETTINGS_DIR = Path("uploads") / "user_settings"
_LIGHTMEM_PATH = _SETTINGS_DIR / "lightmem_preferences.json"

_STORE_LOCK = RLock()
_STORE_CACHE: Optional[Dict[str, Dict[str, object]]] = None


def _ensure_settings_dir() -> None:
    _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def _load_store() -> Dict[str, Dict[str, object]]:
    global _STORE_CACHE  # pylint: disable=global-statement
    if _STORE_CACHE is not None:
        return _STORE_CACHE

    _ensure_settings_dir()
    if not _LIGHTMEM_PATH.exists():
        _STORE_CACHE = {}
        return _STORE_CACHE

    try:
        payload = json.loads(_LIGHTMEM_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            _STORE_CACHE = payload
        else:
            logger.warning("LightMem user settings file is malformed; resetting cache.")
            _STORE_CACHE = {}
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse LightMem user settings: %s", exc)
        _STORE_CACHE = {}
    return _STORE_CACHE


def _save_store(store: Dict[str, Dict[str, object]]) -> None:
    global _STORE_CACHE  # pylint: disable=global-statement
    _ensure_settings_dir()
    _LIGHTMEM_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
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
    digest: bool = True
    chat: bool = True

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, object]]) -> "UserLightMemSettings":
        data = payload or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            watchlist=bool(data.get("watchlist", True)),
            digest=bool(data.get("digest", True)),
            chat=bool(data.get("chat", True)),
        )

    def to_dict(self) -> Dict[str, bool]:
        return {
            "enabled": bool(self.enabled),
            "watchlist": bool(self.watchlist),
            "digest": bool(self.digest),
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


__all__ = [
    "UserLightMemSettings",
    "UserLightMemSettingsRecord",
    "read_user_lightmem_settings",
    "write_user_lightmem_settings",
]
