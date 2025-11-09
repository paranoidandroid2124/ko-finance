from __future__ import annotations

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.digest import DigestSnapshot
from schemas.api.ops import DigestSnapshotListResponse, DigestSnapshotItem, DigestSummaryResponse
from web.deps_ops import require_ops_access

router = APIRouter(prefix="/ops", tags=["Ops"], dependencies=[Depends(require_ops_access)])


@router.get("/digest/summary", response_model=DigestSummaryResponse)
def read_digest_summary(
    timeframe: str = Query(default="daily", description="Summary timeframe label."),
    db: Session = Depends(get_db),
) -> DigestSummaryResponse:
    today = date.today()
    week_start = today - timedelta(days=6)

    today_count = (
        db.query(func.count(DigestSnapshot.id))
        .filter(DigestSnapshot.digest_date == today, DigestSnapshot.timeframe == timeframe)
        .scalar()
        or 0
    )
    last_week_count = (
        db.query(func.count(DigestSnapshot.id))
        .filter(DigestSnapshot.digest_date >= week_start, DigestSnapshot.timeframe == timeframe)
        .scalar()
        or 0
    )
    latest = (
        db.query(DigestSnapshot)
        .filter(DigestSnapshot.timeframe == timeframe)
        .order_by(DigestSnapshot.updated_at.desc())
        .first()
    )

    return DigestSummaryResponse(
        timeframe=timeframe,
        todayCount=int(today_count),
        last7DaysCount=int(last_week_count),
        latestSnapshotAt=latest.updated_at if latest else None,
        latestReferenceDate=latest.digest_date if latest else None,
    )


@router.get("/digest/snapshots", response_model=DigestSnapshotListResponse)
def list_digest_snapshots(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    timeframe: Optional[str] = Query(default=None),
    channel: Optional[str] = Query(default=None),
    reference_date: Optional[date] = Query(default=None),
    user_id: Optional[UUID] = Query(default=None),
    org_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
) -> DigestSnapshotListResponse:
    query = db.query(DigestSnapshot)
    if timeframe:
        query = query.filter(DigestSnapshot.timeframe == timeframe)
    if channel:
        query = query.filter(DigestSnapshot.channel == channel)
    if reference_date:
        query = query.filter(DigestSnapshot.digest_date == reference_date)
    if user_id:
        query = query.filter(DigestSnapshot.user_id == user_id)
    if org_id:
        query = query.filter(DigestSnapshot.org_id == org_id)

    total = query.count()
    rows = (
        query.order_by(DigestSnapshot.digest_date.desc(), DigestSnapshot.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        DigestSnapshotItem(
            id=row.id,
            referenceDate=row.digest_date,
            timeframe=row.timeframe,
            channel=row.channel,
            userId=row.user_id,
            orgId=row.org_id,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
            payload=row.payload,
        )
        for row in rows
    ]
    return DigestSnapshotListResponse(total=total, items=items)
