"""KPI event recording helpers with campaign-driven allowlists."""

from __future__ import annotations

import time
import uuid
from typing import Any, Mapping, Optional, Set

from sqlalchemy.exc import SQLAlchemyError

from services.audit_log import record_audit_event
from services.campaign_settings_service import load_campaign_settings

_DEFAULT_EVENTS: Set[str] = {
    "campaign.starter.banner_view",
    "campaign.starter.banner_click",
    "campaign.starter.banner_dismissed",
    "campaign.starter.settings_cta_click",
}

_ALLOWED_EVENTS_CACHE: Set[str] = set()
_ALLOWED_EVENTS_TS: float = 0.0
_CACHE_TTL_SECONDS = 300


def _refresh_allowed_events() -> None:
    global _ALLOWED_EVENTS_CACHE, _ALLOWED_EVENTS_TS
    settings = load_campaign_settings()
    starter_kpi = settings.get("starter_promo", {}).get("kpi", {})
    dynamic_events = {
        str(name).strip()
        for name in starter_kpi.get("events", []) or []
        if isinstance(name, str) and name.strip()
    }
    _ALLOWED_EVENTS_CACHE = _DEFAULT_EVENTS | dynamic_events
    _ALLOWED_EVENTS_TS = time.monotonic()


def is_allowed_event(name: str) -> bool:
    now = time.monotonic()
    if not _ALLOWED_EVENTS_CACHE or now - _ALLOWED_EVENTS_TS > _CACHE_TTL_SECONDS:
        _refresh_allowed_events()
    return name in _ALLOWED_EVENTS_CACHE


def record_kpi_event(
    *,
    name: str,
    source: str,
    payload: Mapping[str, Any],
    user_id: Optional[uuid.UUID] = None,
    org_id: Optional[uuid.UUID] = None,
) -> None:
    try:
        record_audit_event(
            action=f"kpi.{name}",
            source=source,
            user_id=user_id,
            org_id=org_id,
            extra=dict(payload),
        )
    except SQLAlchemyError:
        # audit service logs internally; swallow to avoid surfacing to clients
        pass


__all__ = ["record_kpi_event", "is_allowed_event"]
