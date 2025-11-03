"""Plan context routes exposing plan tier and entitlements."""

from __future__ import annotations

from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException, status

from schemas.api.plan import (
    PlanContextResponse,
    PlanContextUpdateRequest,
    PlanFeatureFlagsSchema,
    PlanQuotaSchema,
    PlanTier,
)
from services.plan_service import PlanContext, update_plan_context as update_plan_context_service
from web.deps_admin import AdminSession, require_admin_session_for_plan
from web.deps import get_plan_context

router = APIRouter(prefix="/plan", tags=["Plan"])

def _serialize_plan_context(plan: PlanContext, *, checkout_requested: Optional[bool] = None) -> PlanContextResponse:
    feature_flags = plan.feature_flags()
    expires_at = plan.expires_at.isoformat() if plan.expires_at else None
    updated_at = plan.updated_at.isoformat() if plan.updated_at else None
    checkout_flag = plan.checkout_requested if checkout_requested is None else checkout_requested
    return PlanContextResponse(
        planTier=cast(PlanTier, plan.tier),
        expiresAt=expires_at,
        entitlements=sorted(plan.entitlements),
        featureFlags=PlanFeatureFlagsSchema(
            searchCompare=feature_flags.get("search.compare", False),
            searchAlerts=feature_flags.get("search.alerts", False),
            searchExport=feature_flags.get("search.export", False),
            evidenceInlinePdf=feature_flags.get("evidence.inline_pdf", False),
            evidenceDiff=feature_flags.get("evidence.diff", False),
            timelineFull=feature_flags.get("timeline.full", False),
        ),
        quota=PlanQuotaSchema(**plan.quota.to_dict()),
        updatedAt=updated_at,
        updatedBy=plan.updated_by,
        changeNote=plan.change_note,
        checkoutRequested=checkout_flag,
    )


@router.get("/context", response_model=PlanContextResponse, summary="현재 플랜 정보를 반환합니다.")
def read_plan_context(plan: PlanContext = Depends(get_plan_context)) -> PlanContextResponse:
    return _serialize_plan_context(plan)


@router.patch("/context", response_model=PlanContextResponse, summary="플랜 기본값을 저장합니다.")
def patch_plan_context(
    payload: PlanContextUpdateRequest,
    _admin_session: AdminSession = Depends(require_admin_session_for_plan),
) -> PlanContextResponse:
    try:
        updated = update_plan_context_service(
            plan_tier=payload.planTier,
            entitlements=payload.entitlements,
            quota=payload.quota.model_dump(),
            expires_at=payload.expiresAt,
            updated_by=payload.updatedBy,
            change_note=payload.changeNote,
            trigger_checkout=payload.triggerCheckout,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "plan.invalid_payload", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "plan.persist_failed", "message": str(exc)},
        ) from exc
    return _serialize_plan_context(updated)
