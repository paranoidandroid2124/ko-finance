"""Plan context routes exposing plan tier and entitlements."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from schemas.api.plan import (
    PlanCatalogResponse,
    PlanCatalogUpdateRequest,
    PlanContextResponse,
    PlanContextUpdateRequest,
    PlanPresetResponse,
    PlanPresetUpdateRequest,
    PlanTrialStartRequest,
)
from services import plan_config_store
from services.plan_service import (
    PlanContext,
    PlanSettingsConflictError,
    list_plan_presets,
    start_plan_trial as start_plan_trial_service,
    update_plan_context as update_plan_context_service,
)
from services.plan_catalog_service import PlanCatalogConflictError, load_plan_catalog, update_plan_catalog
from services.plan_serializers import (
    serialize_plan_catalog,
    serialize_plan_context,
    serialize_plan_presets,
)
from web.deps import get_plan_context

router = APIRouter(prefix="/plan", tags=["Plan"])


@router.get("/context", response_model=PlanContextResponse, summary="현재 플랜 정보를 반환합니다.")
def read_plan_context(plan: PlanContext = Depends(get_plan_context)) -> PlanContextResponse:
    return serialize_plan_context(plan)


@router.get(
    "/presets",
    response_model=PlanPresetResponse,
    summary="지원되는 플랜 티어의 기본 제공 항목과 쿼터를 반환합니다.",
)
def read_plan_presets() -> PlanPresetResponse:
    payload = list_plan_presets()
    return serialize_plan_presets(payload)


@router.put(
    "/presets",
    response_model=PlanPresetResponse,
    summary="플랜 기본 프리셋(권한/쿼터)을 업데이트합니다.",
)
def update_plan_presets_route(
    payload: PlanPresetUpdateRequest,
) -> PlanPresetResponse:
    plan_config_store.update_plan_config(
        [tier.model_dump() for tier in payload.tiers],
        updated_by=payload.updatedBy,
        note=payload.note,
    )
    plan_config_store.reload_plan_config()
    return serialize_plan_presets(list_plan_presets())


@router.patch("/context", response_model=PlanContextResponse, summary="플랜 기본값을 저장합니다.")
def patch_plan_context(
    payload: PlanContextUpdateRequest,
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
            expected_updated_at=payload.expectedUpdatedAt,
        )
    except PlanSettingsConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "plan.settings_conflict", "message": str(exc)},
        ) from exc
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
    return serialize_plan_context(updated)


@router.post(
    "/trial",
    response_model=PlanContextResponse,
    summary="7일 플랜 체험을 시작합니다.",
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
    return serialize_plan_context(updated)


@router.get(
    "/catalog",
    response_model=PlanCatalogResponse,
    summary="플랜 카탈로그(가격/설명)를 조회합니다.",
)
def read_plan_catalog() -> PlanCatalogResponse:
    payload = load_plan_catalog()
    return serialize_plan_catalog(payload)


@router.put(
    "/catalog",
    response_model=PlanCatalogResponse,
    summary="플랜 카탈로그(가격/설명)를 업데이트합니다.",
)
def update_plan_catalog_route(
    payload: PlanCatalogUpdateRequest,
) -> PlanCatalogResponse:
    try:
        stored = update_plan_catalog(
            [tier.model_dump() for tier in payload.tiers],
            updated_by=payload.updatedBy,
            note=payload.note,
            expected_updated_at=payload.expectedUpdatedAt,
        )
    except PlanCatalogConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "plan.catalog_conflict", "message": str(exc)},
        ) from exc
    return serialize_plan_catalog(stored)
