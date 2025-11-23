"""User profile management (interest tags)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.user_profile import InterestTagRequest, InterestTagsRequest, InterestTagsResponse
from schemas.api.proactive import ProactiveSettingsRequest, ProactiveSettingsResponse
from services import user_profile_service
from services import user_settings_service
from services.web_utils import parse_uuid

router = APIRouter(prefix="/profile", tags=["User Profile"])


def _resolve_user_id(raw: Optional[str]) -> str:
    user_uuid = parse_uuid(raw, detail="사용자 식별자가 필요합니다.")
    if not user_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "profile.user_required", "message": "X-User-Id 헤더가 필요합니다."},
        )
    return str(user_uuid)


@router.get(
    "/interest",
    response_model=InterestTagsResponse,
    summary="사용자 관심 태그를 조회합니다.",
)
def list_interest_tags(
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> InterestTagsResponse:
    user_id = _resolve_user_id(x_user_id)
    tags = user_profile_service.list_interests(user_id)
    return InterestTagsResponse(tags=tags)


@router.post(
    "/interest",
    response_model=InterestTagsResponse,
    summary="관심 태그를 추가합니다.",
)
def add_interest_tag(
    payload: InterestTagRequest,
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> InterestTagsResponse:
    user_id = _resolve_user_id(x_user_id)
    tags = user_profile_service.add_interest(user_id, payload.tag)
    return InterestTagsResponse(tags=tags)


@router.delete(
    "/interest",
    response_model=InterestTagsResponse,
    summary="관심 태그를 삭제합니다.",
)
def remove_interest_tag(
    payload: InterestTagRequest,
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> InterestTagsResponse:
    user_id = _resolve_user_id(x_user_id)
    tags = user_profile_service.remove_interest(user_id, payload.tag)
    return InterestTagsResponse(tags=tags)


@router.put(
    "/interest",
    response_model=InterestTagsResponse,
    summary="관심 태그 전체를 덮어씁니다.",
)
def upsert_interest_tags(
    payload: InterestTagsRequest,
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> InterestTagsResponse:
    user_id = _resolve_user_id(x_user_id)
    tags = user_profile_service.upsert_interests(user_id, payload.tags)
    return InterestTagsResponse(tags=tags)


@router.get(
    "/proactive",
    response_model=ProactiveSettingsResponse,
    summary="프로액티브 알림 설정을 조회합니다.",
)
def get_proactive_settings(
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> ProactiveSettingsResponse:
    user_id = _resolve_user_id(x_user_id)
    record = user_settings_service.read_user_proactive_settings(user_id)
    return ProactiveSettingsResponse(
        enabled=record.settings.enabled,
        channels={
            "widget": record.settings.widget,
            "email": {"enabled": record.settings.email_enabled, "schedule": record.settings.email_schedule},
            "slack": record.settings.slack_enabled,
        },
        preferredTickers=record.settings.preferred_tickers or [],
        blockedTickers=record.settings.blocked_tickers or [],
        preferredSectors=record.settings.preferred_sectors or [],
        blockedSectors=record.settings.blocked_sectors or [],
    )


@router.patch(
    "/proactive",
    response_model=ProactiveSettingsResponse,
    summary="프로액티브 알림 설정을 업데이트합니다.",
)
def update_proactive_settings(
    payload: ProactiveSettingsRequest,
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> ProactiveSettingsResponse:
    user_id = _resolve_user_id(x_user_id)
    record = user_settings_service.read_user_proactive_settings(user_id)
    current = record.settings

    enabled = payload.enabled if payload.enabled is not None else current.enabled
    channels = payload.channels
    widget = channels.widget if channels else current.widget
    email_enabled = channels.email.enabled if channels else current.email_enabled
    email_schedule = channels.email.schedule if channels else current.email_schedule
    slack_enabled = channels.slack if channels else current.slack_enabled
    preferred_tickers = payload.preferredTickers if payload.preferredTickers is not None else current.preferred_tickers
    blocked_tickers = payload.blockedTickers if payload.blockedTickers is not None else current.blocked_tickers
    preferred_sectors = payload.preferredSectors if payload.preferredSectors is not None else current.preferred_sectors
    blocked_sectors = payload.blockedSectors if payload.blockedSectors is not None else current.blocked_sectors

    next_settings = user_settings_service.UserProactiveSettings(
        enabled=enabled,
        widget=widget,
        email_enabled=email_enabled,
        email_schedule=email_schedule,
        slack_enabled=slack_enabled,
        preferred_tickers=preferred_tickers,
        blocked_tickers=blocked_tickers,
        preferred_sectors=preferred_sectors,
        blocked_sectors=blocked_sectors,
    )
    updated = user_settings_service.write_user_proactive_settings(user_id, settings=next_settings)
    return ProactiveSettingsResponse(
        enabled=updated.settings.enabled,
        channels={
            "widget": updated.settings.widget,
            "email": {"enabled": updated.settings.email_enabled, "schedule": updated.settings.email_schedule},
            "slack": updated.settings.slack_enabled,
        },
        preferredTickers=updated.settings.preferred_tickers or [],
        blockedTickers=updated.settings.blocked_tickers or [],
        preferredSectors=updated.settings.preferred_sectors or [],
        blockedSectors=updated.settings.blocked_sectors or [],
    )


__all__ = ["router"]
