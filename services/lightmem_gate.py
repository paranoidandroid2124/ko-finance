"""Shared helpers for LightMem gating used across web and worker contexts."""

from __future__ import annotations

import uuid
from typing import Optional

from services import user_settings_service
from services.lightmem_config import default_user_id as _default_user_id
from services.plan_service import PlanContext


def default_user_id() -> Optional[uuid.UUID]:
    """Return the fallback LightMem user id configured via environment."""
    return _default_user_id()


def load_user_settings(user_id: Optional[uuid.UUID]) -> Optional[user_settings_service.UserLightMemSettings]:
    """Return stored LightMem settings for ``user_id`` if available."""
    if not user_id:
        return None
    try:
        record = user_settings_service.read_user_lightmem_settings(user_id)
        return record.settings
    except Exception:
        return None


def _is_enabled(
    base_flag: bool,
    user_settings: Optional[user_settings_service.UserLightMemSettings],
    attribute: str,
) -> bool:
    if not base_flag:
        return False
    if not user_settings:
        return True
    if not user_settings.enabled:
        return False
    return bool(getattr(user_settings, attribute, False))


def chat_enabled(plan: PlanContext, user_settings: Optional[user_settings_service.UserLightMemSettings]) -> bool:
    """Whether LightMem chat personalization should run."""
    return _is_enabled(plan.memory_chat_enabled, user_settings, "chat")


__all__ = [
    "default_user_id",
    "load_user_settings",
    "chat_enabled",
]
