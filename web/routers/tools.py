"""Commander tool endpoints (event study, disclosure viewer stubs)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.filing import Filing
from models.summary import Summary
from services.agent_tools.event_study_tool import EventStudyNotFoundError, generate_event_study_payload
from services import vector_service

router = APIRouter(prefix="/tools", tags=["Tools"])


class EventStudyRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol (required).")
    event_date: Optional[date] = Field(default=None, description="Target event date (YYYY-MM-DD).")
    window_key: Optional[str] = Field(default=None, description="Preset window key (e.g., D-5~D+5).")
    window: Optional[int] = Field(default=None, description="Symmetric custom window size (overrides window_key).")
    cap_buckets: Optional[List[str]] = Field(default=None, description="Market cap buckets to filter (e.g., ALL/LARGE).")
    markets: Optional[List[str]] = Field(default=None, description="Market codes to filter.")
    significance: Optional[float] = Field(default=None, description="Significance level (default from preset).")


class EventStudyResponse(BaseModel):
    ticker: str
    eventDate: Optional[str] = None
    windowLabel: Optional[str] = None
    winRate: Optional[float] = None
    sampleSize: Optional[int] = None
    caar: Optional[float] = None
    aarSeries: List[dict] = Field(default_factory=list)
    caarSeries: List[dict] = Field(default_factory=list)
    summary: Optional[str] = None


@router.post("/event-study", response_model=EventStudyResponse)
def run_event_study(payload: EventStudyRequest) -> EventStudyResponse:
    """Return condensed event study metrics for the given ticker."""

    try:
        result = generate_event_study_payload(
            ticker=payload.ticker,
            event_date=payload.event_date,
            window_key=payload.window_key,
            window=payload.window,
            cap_buckets=payload.cap_buckets,
            markets=payload.markets,
            significance=payload.significance,
        )
    except EventStudyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="event_study_failed",
        ) from exc

    metrics = result.get("metrics") or {}
    window = result.get("window") or {}
    return EventStudyResponse(
        ticker=result.get("ticker") or payload.ticker,
        eventDate=result.get("eventDate") or result.get("event_date"),
        windowLabel=window.get("label") or window.get("key"),
        winRate=metrics.get("hitRate"),
        sampleSize=metrics.get("sampleSize"),
        caar=metrics.get("meanCaar"),
        aarSeries=metrics.get("aar") or [],
        caarSeries=metrics.get("caar") or [],
        summary=None,
    )


__all__ = ["router"]


class DisclosureHighlight(BaseModel):
    section: Optional[str] = None
    text: Optional[str] = None
    page: Optional[int] = None
    score: Optional[float] = None
    chunk_id: Optional[str] = None
    anchor: Optional[Dict[str, Any]] = None


class DisclosureViewerResponse(BaseModel):
    filing_id: str
    receipt_no: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    pdfViewerUrl: Optional[str] = None
    highlights: List[DisclosureHighlight] = Field(default_factory=list)


def _select_viewer_url(filing: Filing, chunks: List[Dict[str, Any]]) -> Optional[str]:
    # Prefer chunk-level viewer URL if present, otherwise fall back to filing.urls
    for chunk in chunks:
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        for key in ("viewer_url", "document_url", "source_url", "download_url"):
            candidate = metadata.get(key) or chunk.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    urls = filing.urls if isinstance(getattr(filing, "urls", None), dict) else {}
    for key in ("viewer", "pdf_viewer", "download", "pdf"):
        candidate = urls.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


@router.get("/disclosure-viewer", response_model=DisclosureViewerResponse)
def run_disclosure_viewer(
    filing_id: Optional[str] = Query(None, description="Filing UUID"),
    receipt_no: Optional[str] = Query(None, description="DART receipt number"),
    highlight_query: Optional[str] = Query(None, description="Highlight search query"),
    top_k: int = Query(3, ge=1, le=10, description="Max highlights to return"),
    db: Session = Depends(get_db),
):
    """Return highlight candidates for a filing to drive the disclosure viewer."""

    if not filing_id and not receipt_no:
        raise HTTPException(status_code=400, detail={"code": "filing_required", "message": "filing_id or receipt_no is required."})

    query = db.query(Filing)
    if filing_id:
        query = query.filter(Filing.id == filing_id)
    elif receipt_no:
        query = query.filter(Filing.receipt_no == receipt_no)
    filing = query.first()
    if not filing:
        raise HTTPException(status_code=404, detail={"code": "filing_not_found", "message": "Filing not found."})

    question = (highlight_query or filing.title or filing.report_name or "").strip()
    if not question:
        question = "중요 문단"

    filters: Dict[str, Any] = {}
    if filing.ticker:
        filters["ticker"] = filing.ticker

    try:
        retrieval = vector_service.query_vector_store(
            query_text=question,
            filing_id=str(filing.id),
            top_k=top_k,
            max_filings=1,
            filters=filters,
        )
        chunks = retrieval.chunks or []
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "highlight_unavailable", "message": f"검색에 실패했습니다: {exc}"},
        ) from exc

    summary_map: Dict[Any, Summary] = {}
    if filing and chunks:
        summary_entries = db.query(Summary).filter(Summary.filing_id == filing.id).all()
        summary_map = {entry.filing_id: entry for entry in summary_entries}

    highlights: List[DisclosureHighlight] = []
    for chunk in chunks:
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        text = metadata.get("quote") or chunk.get("quote") or chunk.get("content")
        if not text:
            continue
        highlights.append(
            DisclosureHighlight(
                section=metadata.get("section") or chunk.get("section"),
                text=str(text),
                page=metadata.get("page_number") or chunk.get("page_number"),
                score=chunk.get("score"),
                chunk_id=chunk.get("chunk_id") or chunk.get("id"),
                anchor=metadata.get("anchor") or chunk.get("anchor"),
            )
        )
        if len(highlights) >= top_k:
            break

    viewer_url = _select_viewer_url(filing, chunks)
    summary = summary_map.get(filing.id)

    return DisclosureViewerResponse(
        filing_id=str(filing.id),
        receipt_no=filing.receipt_no,
        title=filing.report_name or filing.title,
        company=filing.corp_name or filing.ticker,
        pdfViewerUrl=viewer_url,
        highlights=highlights,
    )
