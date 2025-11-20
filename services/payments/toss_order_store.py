"""Persistent Toss order store used for checkout + webhook status tracking."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from services.json_state_store import JsonStateStore

logger = logging.getLogger(__name__)

_ORDER_STORE_PATH = Path("uploads") / "admin" / "toss_orders.json"
_STATE_KEY = "orders"
_MAX_ORDERS = 400


ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_CONFIRMED = "confirmed"
ORDER_STATUS_PAID = "paid"
ORDER_STATUS_CANCELED = "canceled"
ORDER_STATUS_FAILED = "failed"


@dataclass(slots=True)
class TossOrderRecord:
    order_id: str
    plan_tier: str
    amount: int
    currency: str
    order_name: str
    status: str
    user_id: Optional[str]
    org_id: Optional[str]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


_ORDER_STORE = JsonStateStore(_ORDER_STORE_PATH, _STATE_KEY, logger=logger)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hydrate(item: Mapping[str, Any]) -> Optional[TossOrderRecord]:
    order_id = str(item.get("order_id") or item.get("orderId") or "").strip()
    plan_tier = str(item.get("plan_tier") or item.get("planTier") or "").strip()
    order_name = str(item.get("order_name") or item.get("orderName") or "").strip()
    if not order_id or not plan_tier:
        return None
    amount = int(item.get("amount") or 0)
    currency = str(item.get("currency") or "KRW").strip() or "KRW"
    status = str(item.get("status") or ORDER_STATUS_PENDING).strip() or ORDER_STATUS_PENDING
    created_at = str(item.get("created_at") or item.get("createdAt") or _now_iso()).strip()
    updated_at = str(item.get("updated_at") or item.get("updatedAt") or created_at).strip()
    metadata_raw = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    metadata = dict(metadata_raw) if isinstance(metadata_raw, Mapping) else {}
    user_id = _normalize_optional(item.get("user_id") or item.get("userId"))
    org_id = _normalize_optional(item.get("org_id") or item.get("orgId"))
    if not order_name:
        order_name = f"Nuvien {plan_tier.title()} 플랜"
    return TossOrderRecord(
        order_id=order_id,
        plan_tier=plan_tier,
        amount=amount,
        currency=currency,
        order_name=order_name,
        status=status,
        user_id=user_id,
        org_id=org_id,
        created_at=created_at,
        updated_at=updated_at,
        metadata=metadata,
    )


def _normalize_optional(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_orders(*, reload: bool = False) -> List[TossOrderRecord]:
    items = _ORDER_STORE.load(reload=reload)
    records: List[TossOrderRecord] = []
    for item in items:
        record = _hydrate(item)
        if record:
            records.append(record)
    return records


def _store_orders(records: List[TossOrderRecord]) -> None:
    trimmed = records[-_MAX_ORDERS:]
    payload = [asdict(record) for record in trimmed]
    _ORDER_STORE.store(payload)


def record_checkout(
    *,
    order_id: str,
    plan_tier: str,
    amount: int,
    currency: str,
    order_name: str,
    user_id: Optional[str],
    org_id: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> TossOrderRecord:
    """Persist (or overwrite) a pending checkout order."""
    if not order_id:
        raise ValueError("order_id가 필요합니다.")

    records = [record for record in _load_orders() if record.order_id != order_id]
    now = _now_iso()
    record = TossOrderRecord(
        order_id=order_id,
        plan_tier=plan_tier,
        amount=int(amount),
        currency=currency or "KRW",
        order_name=order_name,
        status=ORDER_STATUS_PENDING,
        user_id=user_id,
        org_id=org_id,
        created_at=now,
        updated_at=now,
        metadata=dict(metadata or {}),
    )
    records.append(record)
    _store_orders(records)
    return record


def update_order_status(
    order_id: str,
    status: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    defaults: Optional[Dict[str, Any]] = None,
) -> Optional[TossOrderRecord]:
    """Update the order status if present; optionally create when defaults are provided."""
    records = _load_orders()
    updated: Optional[TossOrderRecord] = None
    for idx, record in enumerate(records):
        if record.order_id == order_id:
            updated = record
            break

    if updated is None:
        if not defaults:
            return None
        plan_tier = defaults.get("plan_tier")
        amount = int(defaults.get("amount") or 0)
        currency = str(defaults.get("currency") or "KRW")
        order_name = str(defaults.get("order_name") or f"Nuvien {plan_tier or 'Plan'} 플랜 구독")
        if not plan_tier:
            return None
        updated = TossOrderRecord(
            order_id=order_id,
            plan_tier=str(plan_tier),
            amount=amount,
            currency=currency,
            order_name=order_name,
            status=status,
            user_id=_normalize_optional(defaults.get("user_id")),
            org_id=_normalize_optional(defaults.get("org_id")),
            created_at=_now_iso(),
            updated_at=_now_iso(),
            metadata=dict(defaults.get("metadata") or {}),
        )
        records.append(updated)

    updated.status = status
    updated.updated_at = _now_iso()
    if metadata:
        merged = dict(updated.metadata)
        merged.update(metadata)
        updated.metadata = merged

    _store_orders(records)
    return updated


def get_order(order_id: str) -> Optional[TossOrderRecord]:
    """Return order by id if it exists."""
    for record in _load_orders():
        if record.order_id == order_id:
            return record
    return None


def list_orders(*, limit: int = 50) -> List[TossOrderRecord]:
    """Return most recent orders up to ``limit``."""
    records = _load_orders()
    return list(records[-limit:])


def reset_state_for_tests(*, path: Optional[Path] = None) -> None:  # pragma: no cover - testing helper
    """Clear cached state, optionally overriding the backing path."""
    global _ORDER_STORE_PATH, _ORDER_STORE
    if path is not None:
        _ORDER_STORE_PATH = Path(path)
    _ORDER_STORE.reset(path=_ORDER_STORE_PATH)


__all__ = [
    "ORDER_STATUS_CANCELED",
    "ORDER_STATUS_CONFIRMED",
    "ORDER_STATUS_FAILED",
    "ORDER_STATUS_PAID",
    "ORDER_STATUS_PENDING",
    "TossOrderRecord",
    "get_order",
    "list_orders",
    "record_checkout",
    "reset_state_for_tests",
    "update_order_status",
]
