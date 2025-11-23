"""Pydantic schemas for user preference APIs."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UserLightMemSettingsSchema(BaseModel):
    """User-level LightMem opt-in settings."""

    enabled: bool = Field(
        default=False,
        description="전체 LightMem 개인화 사용 여부. False일 경우 모든 LightMem 호출을 차단합니다.",
    )
    chat: bool = Field(
        default=True,
        description="Chat 세션 개인화에 LightMem을 허용할지 여부.",
    )


class UserLightMemSettingsResponse(BaseModel):
    """Response payload describing stored LightMem settings."""

    lightmem: UserLightMemSettingsSchema = Field(..., description="LightMem 개인화 설정.")
    updatedAt: Optional[str] = Field(default=None, description="마지막 갱신 시각 (ISO8601).")
    updatedBy: Optional[str] = Field(default=None, description="설정을 변경한 주체(없으면 null).")


class UserLightMemSettingsUpdateRequest(BaseModel):
    """Update payload for LightMem settings."""

    lightmem: UserLightMemSettingsSchema = Field(..., description="업데이트할 LightMem 개인화 설정.")


__all__ = [
    "UserLightMemSettingsSchema",
    "UserLightMemSettingsResponse",
    "UserLightMemSettingsUpdateRequest",
]
