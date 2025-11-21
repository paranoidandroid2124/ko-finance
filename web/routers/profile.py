"""User profile management (interest tags)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.user_profile import InterestTagRequest, InterestTagsRequest, InterestTagsResponse
from services import user_profile_service
from services.web_utils import parse_uuid

router = APIRouter(prefix="/profile", tags=["User Profile"])


def _resolve_user_id(raw: Optional[str]) -> str:
    user_uuid = parse_uuid(raw, detail="사용자 식별자가 필요합니다.")
    if not user_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "profile.user_required", "message": "X-User-Id 헤더가 필요합니다."},
        )
    return str(user_uuid)


@router.get(
    "/interest",
    response_model=InterestTagsResponse,
    summary="사용자 관심 태그를 조회합니다.",
)
def list_interest_tags(
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> InterestTagsResponse:
    user_id = _resolve_user_id(x_user_id)
    tags = user_profile_service.list_interests(user_id)
    return InterestTagsResponse(tags=tags)


@router.post(
    "/interest",
    response_model=InterestTagsResponse,
    summary="관심 태그를 추가합니다.",
)
def add_interest_tag(
    payload: InterestTagRequest,
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> InterestTagsResponse:
    user_id = _resolve_user_id(x_user_id)
    tags = user_profile_service.add_interest(user_id, payload.tag)
    return InterestTagsResponse(tags=tags)


@router.delete(
    "/interest",
    response_model=InterestTagsResponse,
    summary="관심 태그를 삭제합니다.",
)
def remove_interest_tag(
    payload: InterestTagRequest,
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> InterestTagsResponse:
    user_id = _resolve_user_id(x_user_id)
    tags = user_profile_service.remove_interest(user_id, payload.tag)
    return InterestTagsResponse(tags=tags)


@router.put(
    "/interest",
    response_model=InterestTagsResponse,
    summary="관심 태그 전체를 덮어씁니다.",
)
def upsert_interest_tags(
    payload: InterestTagsRequest,
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> InterestTagsResponse:
    user_id = _resolve_user_id(x_user_id)
    tags = user_profile_service.upsert_interests(user_id, payload.tags)
    return InterestTagsResponse(tags=tags)


__all__ = ["router"]
