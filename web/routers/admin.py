"""Admin quick action and audit endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status

from schemas.api.admin import (
    PlanQuickAdjustRequest,
    PlanQuickAdjustResponse,
    WebhookAuditListResponse,
)
from services.payments.toss_webhook_audit import read_recent_webhook_entries
from services.plan_service import PlanContext, update_plan_context

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/webhooks/toss/events",
    response_model=WebhookAuditListResponse,
    summary="토스 웹훅 감사 로그를 조회합니다.",
)
def list_toss_webhook_audit_entries(limit: int = Query(100, ge=1, le=500)) -> WebhookAuditListResponse:
    items = list(read_recent_webhook_entries(limit=limit))
    return WebhookAuditListResponse(items=items)


@router.post(
    "/plan/quick-adjust",
    response_model=PlanQuickAdjustResponse,
    summary="플랜 티어 및 권한을 신속히 조정합니다.",
)
def apply_plan_quick_adjust(payload: PlanQuickAdjustRequest) -> PlanQuickAdjustResponse:
    quota_overrides: Dict[str, Any] = {}
    if payload.quota is not None:
        quota_overrides = {key: value for key, value in payload.quota.dict().items() if value is not None}

    try:
        context = update_plan_context(
            plan_tier=payload.planTier,
            entitlements=payload.entitlements,
            quota=quota_overrides,
            expires_at=payload.expiresAt,
            updated_by=payload.actor,
            change_note=payload.changeNote,
            trigger_checkout=payload.triggerCheckout,
            force_checkout_requested=payload.forceCheckoutRequested,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "admin.plan_invalid", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.plan_update_failed", "message": str(exc)},
        ) from exc

    return _plan_context_to_response(context)


def _plan_context_to_response(context: PlanContext) -> PlanQuickAdjustResponse:
    return PlanQuickAdjustResponse(
        planTier=context.tier,
        entitlements=sorted(context.entitlements),
        expiresAt=context.expires_at.isoformat() if context.expires_at else None,
        checkoutRequested=context.checkout_requested,
        updatedAt=context.updated_at.isoformat() if context.updated_at else None,
        updatedBy=context.updated_by,
        changeNote=context.change_note,
        quota=context.quota.to_dict(),
    )
