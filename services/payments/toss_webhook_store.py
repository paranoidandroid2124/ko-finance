"""Disk-backed idempotency tracker for Toss webhook events."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_WEBHOOK_STATE_PATH = Path("uploads") / "admin" / "toss_webhook_events.json"
_MAX_RECORDED_EVENTS = 200


@dataclass(slots=True)
class _StoredWebhookEvent:
    key: str
    transmission_id: Optional[str]
    order_id: Optional[str]
    status: Optional[str]
    event_type: Optional[str]
    processed_at: str


_EVENT_CACHE: Optional[List[_StoredWebhookEvent]] = None
_EVENT_CACHE_PATH: Optional[Path] = None


def _load_events(*, reload: bool = False) -> List[_StoredWebhookEvent]:
    global _EVENT_CACHE_PATH, _EVENT_CACHE

    if _event_cache_path_mismatch(_WEBHOOK_STATE_PATH) or reload:
        _EVENT_CACHE = None

    if _EVENT_CACHE is not None:
        return list(_EVENT_CACHE)

    try:
        raw = _WEBHOOK_STATE_PATH.read_text(encoding="utf-8")
        payload = json.loads(raw)
        items = payload.get("events", [])
    except FileNotFoundError:
        items = []
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load Toss webhook state: %s", exc)
        items = []

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

    _EVENT_CACHE = events
    _EVENT_CACHE_PATH = _WEBHOOK_STATE_PATH
    return list(events)


def _event_cache_path_mismatch(path: Path) -> bool:
    return _EVENT_CACHE_PATH is not None and _EVENT_CACHE_PATH != path


def _normalize_optional(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _store_events(events: List[_StoredWebhookEvent]) -> None:
    global _EVENT_CACHE, _EVENT_CACHE_PATH
    data = {"events": [asdict(event) for event in events[-_MAX_RECORDED_EVENTS:]]}
    try:
        path = _WEBHOOK_STATE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to persist Toss webhook state: %s", exc)
        raise
    else:
        _EVENT_CACHE = list(events[-_MAX_RECORDED_EVENTS:])
        _EVENT_CACHE_PATH = _WEBHOOK_STATE_PATH


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
