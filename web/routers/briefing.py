"""Endpoints for F1 daily briefing (proactive insights)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import SessionLocal
from schemas.api.briefing import BriefingItemSchema, BriefingResponse
from services import proactive_briefing_service
from services.lightmem_config import default_user_id as _default_user_id
from services.web_utils import parse_uuid
from web.deps import get_db

router = APIRouter(prefix="/proactive-insights", tags=["Proactive Insights"])


def _resolve_user_id(header_value: Optional[str]) -> uuid.UUID:
    try:
        user_id = parse_uuid(header_value)
    except HTTPException:
        user_id = None
    if user_id:
        return user_id
    fallback = _default_user_id()
    if fallback:
        return fallback
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "briefing.user_required",
            "message": "사용자 식별자가 필요합니다. X-User-Id 헤더를 설정하거나 LIGHTMEM_DEFAULT_USER_ID를 구성하세요.",
        },
    )


@router.get("", response_model=BriefingResponse, summary="가장 최근 프로액티브 인사이트를 조회합니다.")
def read_latest_briefing(x_user_id: Optional[str] = Header(default=None), db: Session = Depends(get_db)) -> BriefingResponse:
    user_id = _resolve_user_id(x_user_id)
    record = proactive_briefing_service.get_latest_briefing(db, user_id=user_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "briefing.not_found", "message": "프로액티브 인사이트가 아직 생성되지 않았습니다."},
        )

    meta = record.meta or {}
    items_payload = meta.get("items") if isinstance(meta, dict) else None
    items = []
    if isinstance(items_payload, list):
        for item in items_payload:
            if not isinstance(item, dict):
                continue
            items.append(
                BriefingItemSchema(
                    title=str(item.get("title") or "브리핑 항목"),
                    summary=item.get("summary"),
                    ticker=item.get("ticker"),
                    targetUrl=item.get("targetUrl"),
                )
            )

    generated_at = None
    if isinstance(meta, dict):
        generated_at = meta.get("generated_at") or meta.get("generatedAt")

    return BriefingResponse(
        id=str(record.id),
        sourceType=record.source_type,
        generatedAt=generated_at,
        title=record.title,
        summary=record.summary,
        items=items,
        meta=meta,
    )


__all__ = ["router"]
