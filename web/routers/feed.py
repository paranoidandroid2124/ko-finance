"""Proactive notification feed endpoints (stub for widget/email delivery)."""

from __future__ import annotations

from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.feed import FeedItemResponse, FeedListResponse
from schemas.api.feed_update import FeedStatusUpdateRequest
from services import proactive_service
from services.web_utils import parse_uuid

router = APIRouter(prefix="/feed", tags=["Feed"])


def _resolve_user_id(raw: Optional[str]) -> str:
    user_uuid = parse_uuid(raw, detail="사용자 식별자가 필요합니다.")
    if not user_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "feed.user_required", "message": "X-User-Id 헤더가 필요합니다."},
        )
    return str(user_uuid)


@router.get(
    "/proactive",
    response_model=FeedListResponse,
    summary="프로액티브 인사이트 피드를 조회합니다.",
)
def list_proactive_feed(
    limit: int = 20,
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> FeedListResponse:
    user_id = uuid.UUID(_resolve_user_id(x_user_id))
    rows = proactive_service.list_notifications(_db, user_id=user_id, limit=limit)
    items: List[FeedItemResponse] = [
        FeedItemResponse(
            id=str(row.id),
            title=row.title,
            summary=row.summary,
            ticker=row.ticker,
            type=row.source_type,
            targetUrl=row.target_url,
            createdAt=row.created_at.isoformat() if row.created_at else None,
            status=row.status,
        )
        for row in rows
    ]
    return FeedListResponse(items=items)


@router.patch(
    "/proactive/{notification_id}",
    response_model=FeedItemResponse,
    summary="알림 상태를 업데이트합니다.",
)
def update_proactive_status(
    notification_id: uuid.UUID,
    payload: FeedStatusUpdateRequest,
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> FeedItemResponse:
    user_id = uuid.UUID(_resolve_user_id(x_user_id))
    updated = proactive_service.update_status(_db, user_id=user_id, notification_id=notification_id, status=payload.status)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "feed.not_found", "message": "알림을 찾을 수 없습니다."},
        )
    return FeedItemResponse(
        id=str(updated.id),
        title=updated.title,
        summary=updated.summary,
        ticker=updated.ticker,
        type=updated.source_type,
        targetUrl=updated.target_url,
        createdAt=updated.created_at.isoformat() if updated.created_at else None,
        status=updated.status,
    )


__all__ = ["router"]
