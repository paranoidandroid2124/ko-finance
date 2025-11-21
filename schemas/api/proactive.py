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


class ProactiveSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    channels: Optional[ProactiveChannels] = None


__all__ = ["EmailChannel", "ProactiveChannels", "ProactiveSettingsResponse", "ProactiveSettingsRequest"]
