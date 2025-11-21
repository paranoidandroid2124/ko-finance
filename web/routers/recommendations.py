"""Recommend starter chat questions based on recent filings and user profile."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.recommendations import RecommendationsResponse
from services import recommendation_service
from services.web_utils import parse_uuid

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get(
    "/chat",
    response_model=RecommendationsResponse,
    summary="추천 질문을 반환합니다 (최근 공시 + 사용자 프로필 기반).",
)
def recommend_chat_starters(
    limit: int = Query(default=3, ge=1, le=10),
    x_user_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> RecommendationsResponse:
    user_id = parse_uuid(x_user_id)
    items = recommendation_service.build_recommendations(
        db,
        user_id=str(user_id) if user_id else None,
        limit=limit,
    )
    return RecommendationsResponse(items=items)


__all__ = ["router"]
