"""Shared helpers for lightmem-aware alerts/watchlist features."""

from __future__ import annotations

import uuid
from typing import Dict, Optional

from services import lightmem_gate
from services.plan_service import PlanContext
from services.user_settings_service import UserLightMemSettings
from services.web_utils import parse_uuid


def default_lightmem_user_id() -> Optional[uuid.UUID]:
    return lightmem_gate.default_user_id()


def resolve_lightmem_user_id(value: Optional[str]) -> Optional[uuid.UUID]:
    if value:
        return parse_uuid(value)
    return default_lightmem_user_id()


def load_user_lightmem_settings(user_id: Optional[uuid.UUID]) -> Optional[UserLightMemSettings]:
    return lightmem_gate.load_user_settings(user_id)


def watchlist_memory_enabled(plan: PlanContext, user_settings: Optional[UserLightMemSettings]) -> bool:
    return lightmem_gate.watchlist_enabled(plan, user_settings)


def digest_memory_enabled(plan: PlanContext, user_settings: Optional[UserLightMemSettings]) -> bool:
    return lightmem_gate.digest_enabled(plan, user_settings)


def owner_filters(user_id: Optional[uuid.UUID], org_id: Optional[uuid.UUID]) -> Dict[str, Optional[uuid.UUID]]:
    return {"user_id": user_id, "org_id": org_id}


__all__ = [
    "default_lightmem_user_id",
    "resolve_lightmem_user_id",
    "load_user_lightmem_settings",
    "watchlist_memory_enabled",
    "digest_memory_enabled",
    "owner_filters",
]
