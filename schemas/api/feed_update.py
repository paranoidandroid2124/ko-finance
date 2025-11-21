from __future__ import annotations

from pydantic import BaseModel, Field


class FeedStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Notification status, e.g., read or dismissed")


__all__ = ["FeedStatusUpdateRequest"]
