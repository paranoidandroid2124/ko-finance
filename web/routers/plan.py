"""Plan context routes exposing plan tier and entitlements."""

from __future__ import annotations

from typing import Any, Dict, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, status

from schemas.api.plan import (
    PlanCatalogResponse,
    PlanCatalogTierSchema,
    PlanCatalogUpdateRequest,
    PlanContextResponse,
    PlanContextUpdateRequest,
    PlanFeatureFlagsSchema,
    PlanMemoryFlagsSchema,
    PlanPresetResponse,
    PlanPresetSchema,
    PlanQuotaSchema,
    PlanTier,
    PlanTrialStartRequest,
    PlanTrialStateSchema,
)
from services.plan_service import (
    PlanContext,
    list_plan_presets,
    start_plan_trial as start_plan_trial_service,
    update_plan_context as update_plan_context_service,
)
from services.plan_catalog_service import load_plan_catalog, update_plan_catalog
from web.deps_admin import AdminSession, require_admin_session_for_plan
from web.deps import get_plan_context

router = APIRouter(prefix="/plan", tags=["Plan"])

def _serialize_plan_context(plan: PlanContext, *, checkout_requested: Optional[bool] = None) -> PlanContextResponse:
    feature_flags = plan.feature_flags()
    memory_flags = plan.memory_flags()
    expires_at = plan.expires_at.isoformat() if plan.expires_at else None
    updated_at = plan.updated_at.isoformat() if plan.updated_at else None
    checkout_flag = plan.checkout_requested if checkout_requested is None else checkout_requested
    trial_payload = plan.trial_payload()
    trial = PlanTrialStateSchema(**trial_payload) if trial_payload else None
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
        memoryFlags=PlanMemoryFlagsSchema(
            watchlist=memory_flags.get("watchlist", False),
            digest=memory_flags.get("digest", False),
            chat=memory_flags.get("chat", False),
        ),
        trial=trial,
    )


@router.get("/context", response_model=PlanContextResponse, summary="현재 플랜 정보를 반환합니다.")
def read_plan_context(plan: PlanContext = Depends(get_plan_context)) -> PlanContextResponse:
    return _serialize_plan_context(plan)


@router.get(
    "/presets",
    response_model=PlanPresetResponse,
    summary="지원되는 플랜 티어의 기본 제공 항목과 쿼터를 반환합니다.",
)
def read_plan_presets() -> PlanPresetResponse:
    payload = list_plan_presets()
    presets: list[PlanPresetSchema] = []
    for preset in payload:
        feature_flags = preset.get("feature_flags", {})
        presets.append(
            PlanPresetSchema(
                tier=cast(PlanTier, preset["tier"]),
                entitlements=list(preset.get("entitlements") or []),
                featureFlags=PlanFeatureFlagsSchema(
                    searchCompare=bool(feature_flags.get("search.compare")),
                    searchAlerts=bool(feature_flags.get("search.alerts")),
                    searchExport=bool(feature_flags.get("search.export")),
                    evidenceInlinePdf=bool(feature_flags.get("evidence.inline_pdf")),
                    evidenceDiff=bool(feature_flags.get("evidence.diff")),
                    timelineFull=bool(feature_flags.get("timeline.full")),
                ),
                quota=PlanQuotaSchema(**cast(Dict[str, Any], preset.get("quota") or {})),
            )
        )
    return PlanPresetResponse(presets=presets)


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
        memory_flags=payload.memoryFlags.model_dump(),
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


@router.post(
    "/trial",
    response_model=PlanContextResponse,
    summary="7ì¼ íŒ€ íŒŒì› ì²´í—˜ì„ ì‹œìž‘í•©ë‹ˆë‹¤.",
)
def start_plan_trial(
    payload: PlanTrialStartRequest,
) -> PlanContextResponse:
    try:
        updated = start_plan_trial_service(
            updated_by=payload.actor,
            target_tier=payload.tier,
            duration_days=payload.durationDays,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "plan.trial_unavailable", "message": str(exc)},
        ) from exc
    return _serialize_plan_context(updated)


def _serialize_catalog_response(payload: Dict[str, Any]) -> PlanCatalogResponse:
    tiers_payload = payload.get("tiers") or []
    tiers = [PlanCatalogTierSchema(**tier) for tier in tiers_payload]
    return PlanCatalogResponse(
        tiers=tiers,
        updatedAt=payload.get("updated_at"),
        updatedBy=payload.get("updated_by"),
        note=payload.get("note"),
    )


@router.get(
    "/catalog",
    response_model=PlanCatalogResponse,
    summary="플랜 카탈로그(가격/설명)를 조회합니다.",
)
def read_plan_catalog() -> PlanCatalogResponse:
    payload = load_plan_catalog()
    return _serialize_catalog_response(payload)


@router.put(
    "/catalog",
    response_model=PlanCatalogResponse,
    summary="플랜 카탈로그(가격/설명)를 업데이트합니다.",
)
def update_plan_catalog_route(
    payload: PlanCatalogUpdateRequest,
    _admin_session: AdminSession = Depends(require_admin_session_for_plan),
) -> PlanCatalogResponse:
    stored = update_plan_catalog(
        [tier.model_dump() for tier in payload.tiers],
        updated_by=payload.updatedBy,
        note=payload.note,
    )
    return _serialize_catalog_response(stored)
