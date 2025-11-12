"KPI analytics schema."

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class KPIEventRequest(BaseModel):
    name: str = Field(..., description="Event name (e.g., campaign.starter.banner_click).")
    source: Optional[str] = Field(default="campaign", description="Logical source of the event.")
    payload: Dict[str, Any] = Field(default_factory=dict)


class KPIEventResponse(BaseModel):
    status: str = "accepted"
