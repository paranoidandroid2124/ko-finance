from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


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
