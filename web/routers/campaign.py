"""Campaign asset/settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from schemas.api.campaign import CampaignSettingsResponse
from services.campaign_settings_service import load_campaign_settings

router = APIRouter(prefix="/campaign", tags=["Campaign"])


@router.get(
    "/settings",
    response_model=CampaignSettingsResponse,
    summary="캠페인 설정(배너/이메일/KPI)을 반환합니다.",
)
def read_campaign_settings() -> CampaignSettingsResponse:
    payload = load_campaign_settings()
    return CampaignSettingsResponse(**payload)


__all__ = ["router"]
