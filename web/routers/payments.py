"""Payment-related API endpoints exposing Toss Payments helpers."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status

from schemas.api.payments import (
    TossPaymentsConfigResponse,
    TossPaymentsConfirmRequest,
    TossPaymentsConfirmResponse,
)
from services.payments import (
    TossPaymentsError,
    get_toss_payments_client,
    get_toss_public_config,
    verify_toss_webhook_signature,
)
from services.payments.toss_webhook_audit import append_webhook_audit_entry
from services.payments.toss_webhook_store import has_processed_webhook, record_webhook_event
from services.payments.toss_webhook_utils import (
    build_webhook_dedupe_key,
    extract_tier_from_order_id,
    resolve_order_id,
    resolve_payment_status,
)
from services.plan_service import PlanTier, SUPPORTED_PLAN_TIERS, apply_checkout_upgrade, clear_checkout_requested

router = APIRouter(prefix="/payments", tags=["Payments"])

logger = logging.getLogger(__name__)


@router.get("/toss/config", response_model=TossPaymentsConfigResponse, summary="토스 결제 위젯 설정을 반환합니다.")
async def read_toss_config() -> TossPaymentsConfigResponse:
    try:
        config = get_toss_public_config()
    except RuntimeError as exc:
        logger.warning("Toss Payments config unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "payments.config_unavailable", "message": str(exc)},
        ) from exc
    return TossPaymentsConfigResponse(**config)


@router.post(
    "/toss/confirm",
    response_model=TossPaymentsConfirmResponse,
    summary="토스 결제를 확인(승인)합니다.",
)
async def confirm_toss_payment(payload: TossPaymentsConfirmRequest) -> TossPaymentsConfirmResponse:
    try:
        client = get_toss_payments_client()
    except RuntimeError as exc:
        logger.error("Toss Payments secret configuration missing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "payments.config_missing", "message": str(exc)},
        ) from exc

    request_payload: Dict[str, Any] = {
        "orderId": payload.orderId,
        "amount": payload.amount,
    }
    try:
        confirmation = await client.confirm_payment(payload.paymentKey, request_payload)
    except TossPaymentsError as exc:
        logger.warning("Toss Payments confirmation failed: %s", exc.payload or exc)
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": "payments.toss_error",
                "message": str(exc),
                "payload": exc.payload,
            },
        ) from exc

    return TossPaymentsConfirmResponse(
        paymentKey=confirmation.get("paymentKey", payload.paymentKey),
        orderId=confirmation.get("orderId", payload.orderId),
        approvedAt=confirmation.get("approvedAt"),
        raw=confirmation,
    )


@router.post(
    "/toss/webhook",
    status_code=status.HTTP_202_ACCEPTED,
    summary="토스 결제 웹훅을 수신합니다.",
)
async def handle_toss_webhook(request: Request) -> Dict[str, str]:
    raw_body = await request.body()
    transmission_time = request.headers.get("tosspayments-webhook-transmission-time")
    signature_header = request.headers.get("tosspayments-webhook-signature")
    transmission_id = request.headers.get("tosspayments-webhook-transmission-id")
    retry_count = request.headers.get("tosspayments-webhook-transmission-retried-count")

    if not transmission_time or not signature_header:
        logger.warning("Toss webhook missing signature headers. transmissionId=%s", transmission_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "payments.webhook_signature_missing", "message": "웹훅 서명 헤더가 누락되었습니다."},
        )

    try:
        is_valid = verify_toss_webhook_signature(
            payload=raw_body,
            transmission_time=transmission_time,
            signature_header=signature_header,
        )
    except RuntimeError as exc:
        logger.error("Toss webhook signature verification unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "payments.webhook_signature_unavailable", "message": str(exc)},
        ) from exc

    if not is_valid:
        logger.warning("Toss webhook signature invalid. transmissionId=%s", transmission_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "payments.webhook_signature_invalid", "message": "웹훅 서명 검증에 실패했습니다."},
        )

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("Toss webhook payload decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "payments.webhook_payload_invalid", "message": "웹훅 본문을 해석하지 못했습니다."},
        ) from exc

    event_type = event.get("eventType")
    base_log_context = {
        "transmission_id": transmission_id,
        "event_type": event_type,
        "retry_count": retry_count,
    }
    logger.info("Received Toss Payments webhook.", extra={"webhook": base_log_context})

    if event_type != "PAYMENT_STATUS_CHANGED":
        logger.info("Ignoring unsupported Toss webhook event.", extra={"webhook": base_log_context})
        append_webhook_audit_entry(
            result="ignored_unsupported_event",
            context=base_log_context,
            payload=event,
        )
        return {"status": "accepted"}

    status_value = resolve_payment_status(event)
    order_id = resolve_order_id(event)
    dedupe_key = build_webhook_dedupe_key(transmission_id, order_id, status_value)

    log_context = {
        **base_log_context,
        "order_id": order_id,
        "status": status_value,
        "dedupe_key": dedupe_key,
    }

    if has_processed_webhook(dedupe_key):
        logger.info("Duplicate Toss webhook ignored.", extra={"webhook": log_context})
        append_webhook_audit_entry(
            result="duplicate",
            context=log_context,
            payload=event,
        )
        return {"status": "accepted"}

    if status_value == "DONE":
        tier = extract_tier_from_order_id(order_id)
        if tier is None:
            logger.error("Unable to infer plan tier from webhook payload.", extra={"webhook": log_context})
            append_webhook_audit_entry(
                result="tier_inference_failed",
                context=log_context,
                payload=event,
                message="플랜 티어 추출에 실패했습니다.",
            )
            record_webhook_event(
                key=dedupe_key,
                transmission_id=transmission_id,
                order_id=order_id,
                status=status_value,
                event_type=event_type,
            )
            return {"status": "accepted"}
        note = f"Toss 결제 완료 ({order_id})"
        try:
            apply_checkout_upgrade(target_tier=tier, updated_by="toss-webhook", change_note=note)
            logger.info(
                "Toss webhook applied plan upgrade.",
                extra={"webhook": {**log_context, "tier": tier}},
            )
            append_webhook_audit_entry(
                result="upgrade_applied",
                context={**log_context, "tier": tier},
                payload=event,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to apply Toss plan upgrade: orderId=%s", order_id)
            append_webhook_audit_entry(
                result="upgrade_failed",
                context={**log_context, "tier": tier},
                payload=event,
                message=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "payments.webhook_plan_update_failed", "message": "플랜 업데이트 중 오류가 발생했습니다."},
            ) from exc
    elif status_value in {"CANCELED", "ABORTED", "EXPIRED"}:
        note = f"Toss 결제 취소 ({order_id})" if order_id else "Toss 결제 취소 처리"
        if order_id:
            try:
                clear_checkout_requested(updated_by="toss-webhook", change_note=note)
                logger.info("Toss webhook cleared checkout flag.", extra={"webhook": log_context})
                append_webhook_audit_entry(
                    result="checkout_cleared",
                    context=log_context,
                    payload=event,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Failed to clear checkout flag for orderId=%s", order_id)
                append_webhook_audit_entry(
                    result="checkout_clear_failed",
                    context=log_context,
                    payload=event,
                    message=str(exc),
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"code": "payments.webhook_checkout_clear_failed", "message": "결제 요청 상태 해제에 실패했습니다."},
                ) from exc
        else:
            logger.info("Toss cancellation webhook missing orderId.", extra={"webhook": log_context})
            append_webhook_audit_entry(
                result="cancel_missing_order",
                context=log_context,
                payload=event,
            )
    else:
        logger.info(
            "Unhandled Toss payment status transition ignored.",
            extra={"webhook": log_context},
        )
        append_webhook_audit_entry(
            result="status_ignored",
            context=log_context,
            payload=event,
        )

    record_webhook_event(
        key=dedupe_key,
        transmission_id=transmission_id,
        order_id=order_id,
        status=status_value,
        event_type=event_type,
    )
    logger.info("Recorded Toss webhook delivery state.", extra={"webhook": log_context})
    append_webhook_audit_entry(
        result="processed",
        context=log_context,
        payload=event,
    )

    return {"status": "accepted"}
