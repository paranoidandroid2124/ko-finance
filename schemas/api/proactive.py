from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class EmailChannel(BaseModel):
    enabled: bool = Field(default=False, description="Email digest enabled")
    schedule: str = Field(default="morning", description="Digest schedule: morning or evening")


class ProactiveChannels(BaseModel):
    widget: bool = Field(default=True, description="Show proactive insights as dashboard/widget cards")
    email: EmailChannel = Field(default_factory=EmailChannel)
    slack: Optional[bool] = Field(default=False, description="Slack channel enabled (future)")


class ProactiveSettingsResponse(BaseModel):
    enabled: bool = False
    channels: ProactiveChannels
    preferredTickers: list[str] = Field(default_factory=list, description="선호 티커 allow 리스트")
    blockedTickers: list[str] = Field(default_factory=list, description="차단 티커 리스트")
    preferredSectors: list[str] = Field(default_factory=list, description="선호 섹터 allow 리스트")
    blockedSectors: list[str] = Field(default_factory=list, description="차단 섹터 리스트")


class ProactiveSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    channels: Optional[ProactiveChannels] = None
    preferredTickers: Optional[list[str]] = None
    blockedTickers: Optional[list[str]] = None
    preferredSectors: Optional[list[str]] = None
    blockedSectors: Optional[list[str]] = None


__all__ = ["EmailChannel", "ProactiveChannels", "ProactiveSettingsResponse", "ProactiveSettingsRequest"]
