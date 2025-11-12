"""Persistent store for Toss order context (org/plan metadata)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from services.json_state_store import JsonStateStore

logger = logging.getLogger(__name__)

_CONTEXT_PATH = Path("uploads") / "admin" / "toss_order_context.json"
_MAX_CONTEXTS = 300
_TTL_HOURS = 72


@dataclass(slots=True)
class OrderContext:
    order_id: str
    org_id: Optional[str]
    plan_slug: Optional[str]
    user_id: Optional[str]
    created_at: str


_CONTEXT_STORE = JsonStateStore(_CONTEXT_PATH, "contexts", logger=logger)


def _load_contexts(*, reload: bool = False) -> List[OrderContext]:
    items = _CONTEXT_STORE.load(reload=reload)
    contexts: List[OrderContext] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        order_id = str(item.get("order_id") or "").strip()
        created_at = str(item.get("created_at") or "").strip()
        if not order_id or not created_at:
            continue
        contexts.append(
            OrderContext(
                order_id=order_id,
                org_id=_normalize_optional(item.get("org_id")),
                plan_slug=_normalize_optional(item.get("plan_slug")),
                user_id=_normalize_optional(item.get("user_id")),
                created_at=created_at,
            )
        )
    return contexts


def _normalize_optional(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _store_contexts(entries: List[OrderContext]) -> None:
    trimmed = entries[-_MAX_CONTEXTS:]
    _CONTEXT_STORE.store([asdict(entry) for entry in trimmed])


def _prune_expired(entries: List[OrderContext]) -> List[OrderContext]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_TTL_HOURS)
    results: List[OrderContext] = []
    for entry in entries:
        try:
            created = datetime.fromisoformat(entry.created_at)
        except ValueError:
            continue
        if created >= cutoff:
            results.append(entry)
    return results


def record_order_context(
    *,
    order_id: str,
    org_id: Optional[str],
    plan_slug: Optional[str],
    user_id: Optional[str],
) -> None:
    """Persist the org/plan metadata for a Toss order."""
    if not order_id:
        return
    entries = _load_contexts()
    filtered = [entry for entry in entries if entry.order_id != order_id]
    created_at = datetime.now(timezone.utc).isoformat()
    filtered.append(
        OrderContext(
            order_id=order_id,
            org_id=_normalize_optional(org_id),
            plan_slug=_normalize_optional(plan_slug),
            user_id=_normalize_optional(user_id),
            created_at=created_at,
        )
    )
    filtered = _prune_expired(filtered)
    _store_contexts(filtered)


def get_order_context(order_id: Optional[str]) -> Optional[OrderContext]:
    """Return stored metadata for ``order_id`` if available."""
    if not order_id:
        return None
    entries = _load_contexts()
    for entry in entries:
        if entry.order_id == order_id:
            return entry
    return None


def pop_order_context(order_id: Optional[str]) -> Optional[OrderContext]:
    """Fetch and remove metadata for ``order_id``."""
    if not order_id:
        return None
    entries = _load_contexts()
    remaining: List[OrderContext] = []
    found: Optional[OrderContext] = None
    for entry in entries:
        if entry.order_id == order_id and found is None:
            found = entry
            continue
        remaining.append(entry)
    if found is not None:
        remaining = _prune_expired(remaining)
        _store_contexts(remaining)
    return found


def reset_state_for_tests(*, path: Optional[Path] = None) -> None:  # pragma: no cover - test helper
    """Reset cached state and optionally override the backing path."""
    global _CONTEXT_PATH
    if path is not None:
        _CONTEXT_PATH = Path(path)
    _CONTEXT_STORE.reset(path=_CONTEXT_PATH)


__all__ = ["OrderContext", "get_order_context", "pop_order_context", "record_order_context", "reset_state_for_tests"]
