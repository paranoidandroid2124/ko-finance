"""Manual replay helpers for Toss webhook events."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from database import SessionLocal
from models.payments import TossWebhookEventLog
from services.payments.toss_webhook_audit import append_webhook_audit_entry
from services.payments.toss_webhook_store import record_webhook_event
from services.payments.toss_webhook_utils import (
    build_webhook_dedupe_key,
    extract_tier_from_order_id,
    resolve_order_id,
    resolve_payment_status,
)
from services.plan_service import apply_checkout_upgrade, clear_checkout_requested

CANCELLATION_STATUSES = {"CANCELED", "ABORTED", "EXPIRED"}


def _load_webhook_record(transmission_id: str) -> Optional[TossWebhookEventLog]:
    session = SessionLocal()
    try:
        return (
            session.query(TossWebhookEventLog)
            .filter(TossWebhookEventLog.transmission_id == transmission_id)
            .order_by(TossWebhookEventLog.created_at.desc())
            .first()
        )
    finally:
        session.close()


def replay_toss_webhook_event(transmission_id: str) -> Dict[str, Any]:
    if not transmission_id:
        raise ValueError("transmission_id가 필요합니다.")

    record = _load_webhook_record(transmission_id)
    if not record or not record.payload:
        raise ValueError("해당 transmissionId에 대한 웹훅 이벤트를 찾을 수 없습니다.")

    event: Dict[str, Any] = record.payload or {}
    context: Dict[str, Any] = record.context or {}

    event_type = event.get("eventType") or context.get("event_type")
    status_value = resolve_payment_status(event) or (record.status or context.get("status"))
    order_id = resolve_order_id(event) or (context.get("order_id") or context.get("orderId"))
    retry_count = context.get("retry_count") or record.retry_count

    base_context = {
        "transmission_id": transmission_id,
        "event_type": event_type,
        "status": status_value,
        "order_id": order_id,
        "retry_count": retry_count,
        "replay": True,
    }

    if event_type != "PAYMENT_STATUS_CHANGED":
        append_webhook_audit_entry(
            result="replay_ignored_event_type",
            context=base_context,
            payload=event,
            message="지원하지 않는 eventType입니다.",
        )
        return {"status": "ignored", "reason": "unsupported_event"}

    if not status_value:
        append_webhook_audit_entry(
            result="replay_status_missing",
            context=base_context,
            payload=event,
            message="이벤트에 status 값이 없습니다.",
        )
        raise ValueError("웹훅 이벤트 status 값을 확인할 수 없습니다.")

    dedupe_key = build_webhook_dedupe_key(transmission_id, order_id, status_value)
    replay_dedupe_key = f"{dedupe_key or transmission_id}:replay:{int(time.time())}"

    if status_value == "DONE":
        tier = extract_tier_from_order_id(order_id)
        if tier is None:
            append_webhook_audit_entry(
                result="replay_tier_inference_failed",
                context=base_context,
                payload=event,
                message="orderId에서 플랜 티어를 추출할 수 없습니다.",
            )
            raise ValueError("orderId에서 플랜 티어를 추출할 수 없습니다.")

        note = f"Toss 결제 수동 재처리 ({order_id})"
        apply_checkout_upgrade(target_tier=tier, updated_by="toss-webhook-replay", change_note=note)
        record_webhook_event(
            key=replay_dedupe_key,
            transmission_id=transmission_id,
            order_id=order_id,
            status=status_value,
            event_type=event_type,
        )
        append_webhook_audit_entry(
            result="replay_upgrade_applied",
            context={**base_context, "tier": tier},
            payload=event,
        )
        return {"status": status_value, "orderId": order_id, "tier": tier}

    if status_value in CANCELLATION_STATUSES:
        note = f"Toss 결제 수동 재처리 취소 ({order_id})" if order_id else "Toss 결제 수동 재처리 취소"
        clear_checkout_requested(updated_by="toss-webhook-replay", change_note=note)
        record_webhook_event(
            key=replay_dedupe_key,
            transmission_id=transmission_id,
            order_id=order_id,
            status=status_value,
            event_type=event_type,
        )
        append_webhook_audit_entry(
            result="replay_checkout_cleared",
            context=base_context,
            payload=event,
        )
        return {"status": status_value, "orderId": order_id}

    append_webhook_audit_entry(
        result="replay_noop",
        context=base_context,
        payload=event,
        message="재처리 대상이 아닌 상태입니다.",
    )
    return {"status": status_value, "orderId": order_id, "noop": True}
