"""Lightweight text-oriented Commander tool endpoints."""

from __future__ import annotations

from typing import Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from database import SessionLocal
from services import market_data, rag_service
from services.plan_service import PlanContext
from web.deps import require_plan_feature

router = APIRouter(prefix="/tools", tags=["Tools"])


def _shorten(text: Optional[str], *, limit: int = 240) -> str:
    if not text:
        return ""
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    trimmed = normalized[: max(0, limit - 3)].rstrip()
    return f"{trimmed}..."


def _build_news_llm_summary(ticker: Optional[str], entries: Iterable[dict]) -> Optional[str]:
    lines: List[str] = []
    for idx, entry in enumerate(entries):
        if idx >= 3:
            break
        summary = _shorten(entry.get("summary"))
        if not summary:
            continue
        title = entry.get("title") or entry.get("source") or f"뉴스 {idx + 1}"
        sentiment = entry.get("sentiment") or "neutral"
        lines.append(f"{idx + 1}. {title}: {summary} (Sentiment: {sentiment})")
    if not lines:
        return None
    subject = ticker or "요청한 종목"
    return f"[News Tool Context] {subject} 관련 최신 요약\n" + "\n".join(lines)


def _build_peer_llm_summary(payload: dict) -> Optional[str]:
    latest_lines: List[str] = []
    for entry in payload.get("latest", []) or []:
        label = entry.get("label") or entry.get("ticker")
        value = entry.get("value")
        if isinstance(value, (int, float)):
            latest_lines.append(f"- {label}: {value:+.2f}%")
    correlation_lines: List[str] = []
    for entry in payload.get("correlations", []) or []:
        label = entry.get("label") or entry.get("ticker")
        value = entry.get("value")
        if isinstance(value, (int, float)):
            correlation_lines.append(f"- {label}: {value:.2f}")
    if not latest_lines and not correlation_lines:
        return None
    parts: List[str] = []
    parts.append(
        f"[Peer Comparison Context] 기준 종목 {payload.get('label') or payload.get('ticker')} · 기간 {payload.get('periodDays')}일"
    )
    if latest_lines:
        parts.append("상대 수익률:\n" + "\n".join(latest_lines))
    interpretation = payload.get("interpretation")
    if isinstance(interpretation, str) and interpretation.strip():
        parts.append(f"해석: {interpretation.strip()}")
    if correlation_lines:
        parts.append("30일 상관계수:\n" + "\n".join(correlation_lines[:3]))
    value_chain_summary = payload.get("valueChainSummary")
    if isinstance(value_chain_summary, str) and value_chain_summary.strip():
        parts.append(f"밸류체인: {value_chain_summary.strip()}")
    return "\n".join(parts)


class NewsRagRequest(BaseModel):
    query: str = Field(..., min_length=1, description="사용자 질문 문장.")
    ticker: str | None = Field(default=None, description="관련 티커 (선택).")
    limit: int = Field(default=6, ge=1, le=20, description="최대 뉴스 카드 수.")


class NewsRagResponse(BaseModel):
    items: list[dict[str, object]]
    llm_summary: str | None = None


@router.post(
    "/news-rag",
    response_model=NewsRagResponse,
    summary="요약된 뉴스 증거를 검색합니다.",
)
def news_rag_tool(
    payload: NewsRagRequest,
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
) -> NewsRagResponse:
    del plan  # reserved for future per-tier limits
    try:
        entries = rag_service.search_news_summaries(payload.query, ticker=payload.ticker, limit=payload.limit)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "news_rag_failed", "message": "뉴스 검색 처리 중 오류가 발생했습니다."},
        ) from exc
    llm_summary = _build_news_llm_summary(payload.ticker, entries)
    return NewsRagResponse(items=entries, llm_summary=llm_summary)


class PeerCompareRequest(BaseModel):
    ticker: str = Field(..., min_length=1, description="기준 종목 코드.")
    period_days: int = Field(default=30, ge=10, le=120, description="상대 비교 기간(거래일 기준).")


class PeerCompareResponse(BaseModel):
    ticker: str
    label: str | None = None
    periodDays: int
    peers: list[dict[str, object]]
    series: list[dict[str, object]]
    latest: list[dict[str, object]]
    interpretation: str
    correlations: list[dict[str, object]]
    llm_summary: str | None = None
    valueChain: dict | None = None
    valueChainSummary: str | None = None


@router.post(
    "/peer-compare",
    response_model=PeerCompareResponse,
    summary="Peer/Sector 상대 비교 데이터를 제공합니다.",
)
def peer_compare_tool(
    payload: PeerCompareRequest,
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
) -> PeerCompareResponse:
    del plan
    session = SessionLocal()
    try:
        comparison = market_data.build_peer_comparison(
            session,
            payload.ticker,
            period_days=payload.period_days,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": str(exc), "message": "비교할 Peer 데이터를 찾지 못했습니다."},
        ) from exc
    finally:
        session.close()
    llm_summary = _build_peer_llm_summary(comparison)
    comparison["llm_summary"] = llm_summary
    return PeerCompareResponse(**comparison)


__all__ = ["router"]
