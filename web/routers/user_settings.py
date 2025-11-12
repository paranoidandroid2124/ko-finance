"""User-facing settings endpoints."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from schemas.api.user_settings import (
    UserLightMemSettingsResponse,
    UserLightMemSettingsSchema,
    UserLightMemSettingsUpdateRequest,
)
from services import lightmem_gate, user_settings_service
from services.plan_service import PlanContext
from web.deps import get_plan_context

router = APIRouter(prefix="/user-settings", tags=["User Settings"])


def _parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _resolve_user_id(header_value: Optional[str]) -> uuid.UUID:
    user_id = _parse_uuid(header_value)
    if user_id:
        return user_id
    fallback = lightmem_gate.default_user_id()
    if fallback:
        return fallback
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "user_settings.user_required",
            "message": "사용자 식별자가 필요합니다. X-User-Id 헤더를 설정하거나 LIGHTMEM_DEFAULT_USER_ID를 구성하세요.",
        },
    )


def _serialize(record: user_settings_service.UserLightMemSettingsRecord) -> UserLightMemSettingsResponse:
    settings = record.settings
    return UserLightMemSettingsResponse(
        lightmem=UserLightMemSettingsSchema(
            enabled=settings.enabled,
            watchlist=settings.watchlist,
            digest=settings.digest,
            chat=settings.chat,
        ),
        updatedAt=record.updated_at.isoformat() if record.updated_at else None,
        updatedBy=record.updated_by,
    )


def _ensure_lightmem_allowed(plan: PlanContext, settings: UserLightMemSettingsSchema) -> None:
    plan_flags = plan.memory_flags()
    if settings.enabled and not any(plan_flags.values()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "plan.lightmem_unavailable",
                "message": "현재 플랜에서는 LightMem 개인화를 사용할 수 없습니다. Pro 이상 플랜으로 업그레이드해주세요.",
                "planTier": plan.tier,
            },
        )

    feature_labels = {
        "watchlist": "워치리스트",
        "digest": "다이제스트",
        "chat": "대화 메모리",
    }
    for key, allowed in feature_labels.items():
        plan_allows = bool(plan_flags.get(key, False))
        requested = bool(getattr(settings, key))
        if requested and not plan_allows:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": f"plan.lightmem_{key}_locked",
                    "message": f"{allowed} 기능은 Pro 이상 플랜에서만 사용할 수 있습니다.",
                    "planTier": plan.tier,
                },
            )


@router.get(
    "/lightmem",
    response_model=UserLightMemSettingsResponse,
    summary="사용자별 LightMem 개인화 설정을 조회합니다.",
)
def read_lightmem_settings(x_user_id: Optional[str] = Header(default=None)) -> UserLightMemSettingsResponse:
    user_id = _resolve_user_id(x_user_id)
    record = user_settings_service.read_user_lightmem_settings(user_id)
    return _serialize(record)


@router.put(
    "/lightmem",
    response_model=UserLightMemSettingsResponse,
    summary="사용자별 LightMem 개인화 설정을 업데이트합니다.",
)
def update_lightmem_settings(
    payload: UserLightMemSettingsUpdateRequest,
    x_user_id: Optional[str] = Header(default=None),
    plan: PlanContext = Depends(get_plan_context),
) -> UserLightMemSettingsResponse:
    user_id = _resolve_user_id(x_user_id)
    _ensure_lightmem_allowed(plan, payload.lightmem)
    record = user_settings_service.write_user_lightmem_settings(
        user_id=user_id,
        settings=user_settings_service.UserLightMemSettings(
            enabled=payload.lightmem.enabled,
            watchlist=payload.lightmem.watchlist,
            digest=payload.lightmem.digest,
            chat=payload.lightmem.chat,
        ),
        actor=str(user_id),
    )
    return _serialize(record)


__all__ = ["router"]
