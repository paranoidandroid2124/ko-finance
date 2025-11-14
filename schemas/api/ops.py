from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DigestSnapshotItem(BaseModel):
    id: UUID
    referenceDate: date
    timeframe: str
    channel: str
    userId: Optional[UUID]
    orgId: Optional[UUID]
    createdAt: datetime
    updatedAt: datetime
    payload: Dict[str, Any]


class DigestSnapshotListResponse(BaseModel):
    total: int
    items: List[DigestSnapshotItem]


class DigestSummaryResponse(BaseModel):
    timeframe: str
    todayCount: int
    last7DaysCount: int
    latestSnapshotAt: Optional[datetime]
    latestReferenceDate: Optional[date]


class CeleryScheduleEntry(BaseModel):
    task: str
    cron: str
    args: List[Any] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)


class CeleryScheduleResponse(BaseModel):
    timezone: Optional[str]
    path: Optional[str]
    entries: Dict[str, CeleryScheduleEntry]
