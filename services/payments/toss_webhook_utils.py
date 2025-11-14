"""Shared helpers for Toss webhook processing."""

from __future__ import annotations

from typing import Any, Dict, Optional, cast

from core.plan_constants import PlanTier, SUPPORTED_PLAN_TIERS


def resolve_payment_status(event: Dict[str, Any]) -> Optional[str]:
    data = event.get("data") or {}
    status_value = data.get("status") or event.get("status")
    if isinstance(status_value, str):
        return status_value.upper()
    return None


def resolve_order_id(event: Dict[str, Any]) -> Optional[str]:
    data = event.get("data") or {}
    order_id = data.get("orderId") or event.get("orderId")
    if isinstance(order_id, str):
        return order_id
    return None


def extract_tier_from_order_id(order_id: Optional[str]) -> Optional[PlanTier]:
    if not order_id:
        return None
    parts = order_id.split("-")
    if len(parts) < 3:
        return None
    prefix, tier_candidate = parts[0], parts[1]
    if prefix != "kfinance":
        return None
    if tier_candidate not in SUPPORTED_PLAN_TIERS:
        return None
    return cast(PlanTier, tier_candidate)


def build_webhook_dedupe_key(
    transmission_id: Optional[str],
    order_id: Optional[str],
    status_value: Optional[str],
) -> Optional[str]:
    if transmission_id:
        return transmission_id
    if order_id and status_value:
        return f"{order_id}:{status_value}"
    if order_id:
        return order_id
    return None
