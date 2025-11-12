"""Disk-backed idempotency tracker for Toss webhook events."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_WEBHOOK_STATE_PATH = Path("uploads") / "admin" / "toss_webhook_events.json"
_MAX_RECORDED_EVENTS = 200

from services.json_state_store import JsonStateStore


@dataclass(slots=True)
class _StoredWebhookEvent:
    key: str
    transmission_id: Optional[str]
    order_id: Optional[str]
    status: Optional[str]
    event_type: Optional[str]
    processed_at: str


_EVENT_STORE = JsonStateStore(_WEBHOOK_STATE_PATH, "events", logger=logger)


def _load_events(*, reload: bool = False) -> List[_StoredWebhookEvent]:
    items = _EVENT_STORE.load(reload=reload)
    events: List[_StoredWebhookEvent] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        processed_at = str(item.get("processed_at") or "").strip()
        if not key or not processed_at:
            continue
        events.append(
            _StoredWebhookEvent(
                key=key,
                transmission_id=_normalize_optional(item.get("transmission_id")),
                order_id=_normalize_optional(item.get("order_id")),
                status=_normalize_optional(item.get("status")),
                event_type=_normalize_optional(item.get("event_type")),
                processed_at=processed_at,
            )
        )

    return list(events)


def _normalize_optional(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _store_events(events: List[_StoredWebhookEvent]) -> None:
    trimmed = events[-_MAX_RECORDED_EVENTS:]
    _EVENT_STORE.store([asdict(event) for event in trimmed])


def has_processed_webhook(key: Optional[str]) -> bool:
    """Return True if the webhook key has already been processed recently."""
    if not key:
        return False
    events = _load_events()
    return any(event.key == key for event in events)


def record_webhook_event(
    *,
    key: Optional[str],
    transmission_id: Optional[str],
    order_id: Optional[str],
    status: Optional[str],
    event_type: Optional[str],
) -> None:
    """Persist that the webhook identified by ``key`` has been processed."""
    if not key:
        return

    events = _load_events()
    filtered = [event for event in events if event.key != key]

    processed_at = datetime.now(timezone.utc).isoformat()
    filtered.append(
        _StoredWebhookEvent(
            key=key,
            transmission_id=transmission_id,
            order_id=order_id,
            status=status,
            event_type=event_type,
            processed_at=processed_at,
        )
    )

    _store_events(filtered)


def reset_state_for_tests(*, path: Optional[Path] = None) -> None:  # pragma: no cover - testing helper
    """Clear cached state and optionally point storage to a new path."""
    global _WEBHOOK_STATE_PATH, _EVENT_STORE
    if path is not None:
        _WEBHOOK_STATE_PATH = Path(path)
    _EVENT_STORE.reset(path=_WEBHOOK_STATE_PATH)
