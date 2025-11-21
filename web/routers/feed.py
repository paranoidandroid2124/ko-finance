"""Proactive notification feed endpoints (stub for widget/email delivery)."""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence, Tuple
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from core.env import env_float
from database import get_db
from schemas.api.feed import FeedItemResponse, FeedListResponse
from schemas.api.feed_update import FeedStatusUpdateRequest
from schemas.api.feed_briefing import FeedBriefing, FeedBriefingListResponse
from services import proactive_service
from services.web_utils import parse_uuid
import llm.llm_service as llm_service

router = APIRouter(prefix="/feed", tags=["Feed"])
CLUSTER_THRESHOLD = env_float("PROACTIVE_CLUSTER_THRESHOLD", 0.8)
HEADLINE_TTL_SECONDS = env_float("PROACTIVE_HEADLINE_TTL", 600.0)
_headline_cache: Dict[str, Tuple[str, float]] = {}


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


def _make_briefing_title(cluster_key: str, items: List[FeedItemResponse]) -> str:
    base = cluster_key or "새 소식"
    return f"{base} 관련 인사이트"


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _extract_embedding(metadata: Optional[dict]) -> Optional[List[float]]:
    if not isinstance(metadata, dict):
        return None
    raw = metadata.get("embedding")
    if not isinstance(raw, list) or not raw:
        return None
    try:
        return [float(x) for x in raw]
    except (TypeError, ValueError):
        return None


def _cluster_entries(entries: List[dict]) -> List[List[dict]]:
    clusters: List[List[dict]] = []
    for entry in entries:
        emb = entry.get("embedding")
        if not emb:
            clusters.append([entry])
            continue
        matched_cluster: Optional[List[dict]] = None
        for cluster in clusters:
            rep = cluster[0].get("embedding")
            if rep and _cosine(emb, rep) >= CLUSTER_THRESHOLD:
                matched_cluster = cluster
                break
        if matched_cluster is not None:
            matched_cluster.append(entry)
        else:
            clusters.append([entry])
    return clusters


def _headline_cache_key(items: List[FeedItemResponse]) -> str:
    ids = sorted([item.id for item in items if item.id])
    return "|".join(ids)


def _summaries_text(items: List[FeedItemResponse]) -> str:
    lines = []
    for item in items[:5]:
        snippet = item.summary or item.title or ""
        ticker = f"[{item.ticker}]" if item.ticker else ""
        if snippet:
            lines.append(f"- {ticker} {snippet}".strip())
    return "\n".join(lines) or "요약 불가"


def _generate_headline(items: List[FeedItemResponse]) -> Optional[str]:
    cache_key = _headline_cache_key(items)
    now = time.time()
    cached = _headline_cache.get(cache_key)
    if cached and now - cached[1] < HEADLINE_TTL_SECONDS:
        return cached[0]

    content = _summaries_text(items)
    messages = [
        {
            "role": "system",
            "content": "너는 금융 미디어의 헤드라인 에디터다. 아래 이벤트들을 한 줄 한국어 헤드라인으로 압축해라. 군더더기 없이 간결하게.",
        },
        {
            "role": "user",
            "content": content,
        },
    ]
    try:
        response, _ = llm_service._safe_completion(llm_service.SUMMARY_MODEL, messages)  # type: ignore[attr-defined]
        headline = (response.choices[0].message.content or "").strip()
        if headline:
            _headline_cache[cache_key] = (headline, now)
            return headline
    except Exception:
        return None
    return None


@router.get(
    "/proactive/briefings",
    response_model=FeedBriefingListResponse,
    summary="프로액티브 알림을 주제별로 묶어 요약합니다.",
)
def list_proactive_briefings(
    limit: int = 30,
    x_user_id: Optional[str] = Header(default=None),
    _db: Session = Depends(get_db),
) -> FeedBriefingListResponse:
    user_id = uuid.UUID(_resolve_user_id(x_user_id))
    rows = proactive_service.list_notifications(_db, user_id=user_id, limit=limit)
    entries: List[dict] = []
    for row in rows:
        item = FeedItemResponse(
            id=str(row.id),
            title=row.title,
            summary=row.summary,
            ticker=row.ticker,
            type=row.source_type,
            targetUrl=row.target_url,
            createdAt=row.created_at.isoformat() if row.created_at else None,
            status=row.status,
        )
        entries.append(
            {
                "item": item,
                "embedding": _extract_embedding(getattr(row, "metadata", None)),
            }
        )

    clustered_entries = _cluster_entries(entries)
    clusters: List[FeedBriefing] = []
    for group in clustered_entries:
        if not group:
            continue
        items = [entry["item"] for entry in group]
        tickers = {itm.ticker for itm in items if itm.ticker}
        ticker = items[0].ticker if len(tickers) == 1 else None
        headline = _generate_headline(items)
        title = headline or _make_briefing_title(ticker or items[0].type or "general", items)
        summary = next((itm.summary for itm in items if itm.summary), None)
        clusters.append(
            FeedBriefing(
                id=str(uuid.uuid4()),
                title=title,
                summary=summary,
                ticker=ticker,
                count=len(items),
                items=items,
            )
        )

    # 최신순 정렬 (첫 아이템 createdAt)
    clusters.sort(
        key=lambda c: c.items[0].createdAt if c.items and c.items[0].createdAt else "",
        reverse=True,
    )
    return FeedBriefingListResponse(items=clusters)
