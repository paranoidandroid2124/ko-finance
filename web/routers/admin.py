"""Admin quick action and audit endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status

from schemas.api.admin import (
    PlanQuickAdjustRequest,
    TossWebhookReplayRequest,
    TossWebhookReplayResponse,
    WebhookAuditListResponse,
)
from schemas.api.plan import PlanContextResponse, PlanFeatureFlagsSchema, PlanQuotaSchema
from services.payments.toss_webhook_audit import read_recent_webhook_entries
from services.payments.toss_webhook_replay import replay_toss_webhook_event
from services.plan_service import PlanContext, update_plan_context

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/webhooks/toss/events",
    response_model=WebhookAuditListResponse,
    summary="?? ?? ?? ??? ?????.",
)
def list_toss_webhook_audit_entries(limit: int = Query(100, ge=1, le=500)) -> WebhookAuditListResponse:
    items = list(read_recent_webhook_entries(limit=limit))
    return WebhookAuditListResponse(items=items)


@router.post(
    "/webhooks/toss/replay",
    response_model=TossWebhookReplayResponse,
    summary="?? ?? ???? ???? ??????.",
)
def replay_toss_webhook(payload: TossWebhookReplayRequest) -> TossWebhookReplayResponse:
    try:
        result = replay_toss_webhook_event(payload.transmissionId)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "admin.webhook_replay_invalid", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.webhook_replay_failed", "message": str(exc)},
        ) from exc

    return TossWebhookReplayResponse(**result)


@router.post(
    "/plan/quick-adjust",
    response_model=PlanContextResponse,
    summary="?? ?? ? ??? ??? ?????.",
)
def apply_plan_quick_adjust(payload: PlanQuickAdjustRequest) -> PlanContextResponse:
    quota_overrides: Dict[str, Any] = {}
    if payload.quota is not None:
        quota_overrides = payload.quota.model_dump(exclude_none=True)

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


def _plan_context_to_response(context: PlanContext) -> PlanContextResponse:
    feature_flags = context.feature_flags()
    return PlanContextResponse(
        planTier=context.tier,
        entitlements=sorted(context.entitlements),
        expiresAt=context.expires_at.isoformat() if context.expires_at else None,
        checkoutRequested=context.checkout_requested,
        updatedAt=context.updated_at.isoformat() if context.updated_at else None,
        updatedBy=context.updated_by,
        changeNote=context.change_note,
        quota=PlanQuotaSchema(**context.quota.to_dict()),
        featureFlags=PlanFeatureFlagsSchema(
            searchCompare=feature_flags.get("search.compare", False),
            searchAlerts=feature_flags.get("search.alerts", False),
            searchExport=feature_flags.get("search.export", False),
            evidenceInlinePdf=feature_flags.get("evidence.inline_pdf", False),
            evidenceDiff=feature_flags.get("evidence.diff", False),
            timelineFull=feature_flags.get("timeline.full", False),
        ),
    )
