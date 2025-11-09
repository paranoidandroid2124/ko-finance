"""Lightweight public/unauthenticated preview endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from models.filing import Filing
from schemas.api.public import (
    PublicChatRequest,
    PublicChatResponse,
    PublicChatSource,
    PublicFiling,
    PublicFilingsResponse,
)

try:  # pragma: no cover - redis may be optional
    from services.lightmem_rate_limiter import RateLimitResult, check_limit as _check_limit
except Exception:  # pragma: no cover - fallback to allow traffic without Redis

    class RateLimitResult:  # type: ignore[no-redef]
        def __init__(self, allowed: bool = True):
            self.allowed = allowed

    def _check_limit(*args, **kwargs):  # type: ignore[no-redef]
        return RateLimitResult()

router = APIRouter(prefix="/public", tags=["Public"])

_MAX_FILINGS = 10
_DEFAULT_LIMIT = 5
_CHAT_DISCLAIMER = "이 미리보기 대화는 저장되지 않으며, 상세 분석과 히스토리는 로그인 후 이용할 수 있습니다."


def _client_identifier(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return None


def _enforce_public_rate_limit(scope: str, identifier: Optional[str], *, limit: int, window_seconds: int) -> None:
    result: RateLimitResult = _check_limit(scope, identifier, limit=limit, window_seconds=window_seconds)  # type: ignore[arg-type]
    if not getattr(result, "allowed", True):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "public.rate_limited", "message": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."},
        )


def _serialize_filing(filing: Filing) -> PublicFiling:
    filed_ts = filing.filed_at or filing.created_at
    highlight_parts = [
        part for part in [filing.report_name, filing.title, filing.category, filing.market] if part
    ]
    highlight = " · ".join(highlight_parts[:3]) if highlight_parts else None
    target_url = f"/filings?filingId={filing.id}" if filing.id else None
    return PublicFiling(
        id=str(filing.id),
        corpName=filing.corp_name or filing.ticker,
        reportName=filing.report_name or filing.title,
        category=filing.category,
        market=filing.market,
        filedAt=filed_ts,
        highlight=highlight,
        targetUrl=target_url,
    )


def _fetch_recent_filings(db: Session, *, limit: int) -> List[Filing]:
    limit = max(1, min(limit, _MAX_FILINGS))
    order_expr = func.coalesce(Filing.filed_at, Filing.created_at).desc()
    rows = (
        db.query(Filing)
        .filter(
            or_(
                Filing.filed_at.isnot(None),
                Filing.created_at.isnot(None),
            )
        )
        .order_by(order_expr)
        .limit(limit)
        .all()
    )
    return list(rows)


def _build_chat_answer(question: str, filings: Iterable[Filing]) -> Tuple[str, List[PublicChatSource]]:
    filings_list = list(filings)
    lines: List[str] = []
    sources: List[PublicChatSource] = []
    for filing in filings_list:
        filed_ts = filing.filed_at or filing.created_at
        filed_display = filed_ts.isoformat(timespec="seconds") if filed_ts else "날짜 정보 없음"
        corp = filing.corp_name or filing.ticker or "기업"
        report = filing.report_name or filing.title or "공시"
        category = filing.category or "공시"
        lines.append(f"- {filed_display[:10]} {corp} · {report} ({category})")
        sources.append(
            PublicChatSource(
                id=str(filing.id),
                title=f"{corp} · {report}",
                summary=filing.notes or filing.title or filing.report_name,
                filedAt=filed_ts,
                targetUrl=f"/filings?filingId={filing.id}" if filing.id else None,
            )
        )

    normalized_question = question.strip()
    if filings_list:
        joined = "\n".join(lines)
        answer = (
            f"질문 요약: \"{normalized_question}\".\n"
            "바로 확인 가능한 최신 공시는 다음과 같습니다:\n"
            f"{joined}\n\n"
            "심층 리서치와 맞춤형 Q&A는 로그인 후 RAG 챗에서 이어갈 수 있습니다."
        )
    else:
        answer = (
            f"질문 요약: \"{normalized_question}\".\n"
            "아직 공개 미리보기용 공시 데이터가 준비되지 않았습니다. "
            "로그인하면 전체 데이터셋과 RAG 챗 기능을 사용할 수 있습니다."
        )
    return answer, sources


@router.get("/filings", response_model=PublicFilingsResponse)
def read_public_filings(limit: int = _DEFAULT_LIMIT, db: Session = Depends(get_db)) -> PublicFilingsResponse:
    filings = _fetch_recent_filings(db, limit=limit)
    serialized = [_serialize_filing(filing) for filing in filings]
    return PublicFilingsResponse(filings=serialized)


@router.post("/chat", response_model=PublicChatResponse)
def create_public_chat_preview(
    payload: PublicChatRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PublicChatResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "public.invalid_question", "message": "질문을 입력해 주세요."},
        )

    identifier = _client_identifier(request)
    _enforce_public_rate_limit("public.chat", identifier, limit=5, window_seconds=3600)

    filings = _fetch_recent_filings(db, limit=3)
    answer, sources = _build_chat_answer(question, filings)

    return PublicChatResponse(answer=answer, sources=sources, disclaimer=_CHAT_DISCLAIMER)
