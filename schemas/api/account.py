from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DSARRequestSummary(BaseModel):
    id: UUID
    requestType: Literal["export", "delete"]
    status: Literal["pending", "processing", "completed", "failed"]
    channel: str
    requestedAt: datetime
    completedAt: Optional[datetime] = None
    artifactPath: Optional[str] = None
    failureReason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DSARRequestListResponse(BaseModel):
    requests: List[DSARRequestSummary]
    pendingCount: int
    hasActiveRequest: bool = False


class DSARRequestCreate(BaseModel):
    requestType: Literal["export", "delete"]
    note: Optional[str] = None


__all__ = [
    "DSARRequestSummary",
    "DSARRequestListResponse",
    "DSARRequestCreate",
]
