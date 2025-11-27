import uuid
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.logging import get_logger
from database import get_db
from models.fact import ExtractedFact
from models.filing import Filing
from models.summary import Summary
from schemas.api.filing import (
    FactResponse,
    FilingBriefResponse,
    FilingDetailResponse,
    FilingXmlDocument,
    FilingXmlResponse,
    SummaryResponse,
)
from services import storage_service, filing_jobs, filing_fetch_service

router = APIRouter(prefix="/filings", tags=["Filings"])
logger = get_logger(__name__)

CATEGORY_TRANSLATIONS = {
    "capital_increase": "증자",
    "증자": "증자",
    "buyback": "자사주 매입/소각",
    "share_buyback": "자사주 매입/소각",
    "자사주 매입/소각": "자사주 매입/소각",
    "cb_bw": "전환사채·신주인수권부사채",
    "convertible": "전환사채·신주인수권부사채",
    "전환사채·신주인수권부사채": "전환사채·신주인수권부사채",
    "large_contract": "대규모 공급·수주 계약",
    "major_contract": "대규모 공급·수주 계약",
    "대규모 공급·수주 계약": "대규모 공급·수주 계약",
    "litigation": "소송/분쟁",
    "lawsuit": "소송/분쟁",
    "소송/분쟁": "소송/분쟁",
    "mna": "M&A/합병·분할",
    "m&a": "M&A/합병·분할",
    "합병": "M&A/합병·분할",
    "governance": "지배구조·임원 변경",
    "governance_change": "지배구조·임원 변경",
    "지배구조·임원 변경": "지배구조·임원 변경",
    "audit_opinion": "감사 의견",
    "감사 의견": "감사 의견",
    "periodic_report": "정기·수시 보고서",
    "regular_report": "정기·수시 보고서",
    "정기·수시 보고서": "정기·수시 보고서",
    "securities_registration": "증권신고서/투자설명서",
    "registration": "증권신고서/투자설명서",
    "증권신고서/투자설명서": "증권신고서/투자설명서",
    "insider_ownership": "임원·주요주주 지분 변동",
    "insider_trading": "임원·주요주주 지분 변동",
    "임원·주요주주 지분 변동": "임원·주요주주 지분 변동",
    "correction": "정정 공시",
    "revision": "정정 공시",
    "정정 공시": "정정 공시",
    "ir_presentation": "IR/설명회",
    "ir": "IR/설명회",
    "ir/설명회": "IR/설명회",
    "dividend": "배당/주주환원",
    "shareholder_return": "배당/주주환원",
    "배당/주주환원": "배당/주주환원",
    "other": "기타",
    "기타": "기타",
}

CATEGORY_WEIGHTS = {
    "M&A/합병·분할": 1.0,
    "전환사채·신주인수권부사채": 0.9,
    "증자": 0.85,
    "자사주 매입/소각": 0.85,
    "배당/주주환원": 0.8,
    "대규모 공급·수주 계약": 0.75,
    "정기·수시 보고서": 0.6,
    "지배구조·임원 변경": 0.6,
    "감사 의견": 0.55,
    "정정 공시": 0.5,
    "기타": 0.2,
}
HIGHLIGHT_CATEGORY_SET = {
    "M&A/합병·분할",
    "전환사채·신주인수권부사채",
    "증자",
    "자사주 매입/소각",
    "배당/주주환원",
    "대규모 공급·수주 계약",
    "정기·수시 보고서",
    "지배구조·임원 변경",
    "감사 의견",
    "정정 공시",
}

POSITIVE_CATEGORIES = {
    "자사주 매입/소각",
    "대규모 공급·수주 계약",
    "배당/주주환원",
    "M&A/합병·분할",
}
NEGATIVE_CATEGORIES = {
    "소송/분쟁",
    "감사 의견",
    "정정 공시",
}

SUMMARY_SENTIMENT_LABELS = {"positive", "neutral", "negative"}

POSITIVE_KEYWORDS = {
    "increase",
    "surge",
    "order",
    "contract",
    "improvement",
    "expansion",
    "favorable",
    "dividend",
    "buyback",
    "증가",
    "수주",
    "계약",
    "개선",
    "확대",
    "호재",
    "배당",
    "자사주",
}
NEGATIVE_KEYWORDS = {
    "decrease",
    "drop",
    "loss",
    "lawsuit",
    "suspend",
    "cancel",
    "violate",
    "discipline",
    "warning",
    "risk",
    "감소",
    "하락",
    "손실",
    "소송",
    "취소",
    "위험",
    "경고",
    "분쟁",
}

_AMOUNT_PATTERN = r"([0-9]+(?:\.[0-9]+)?)\s*(조|억)"


def _normalize_category_label(value: Optional[str]) -> str:
    if not value:
        return ""
    trimmed = value.strip()
    lower = trimmed.lower()
    return CATEGORY_TRANSLATIONS.get(lower) or CATEGORY_TRANSLATIONS.get(trimmed) or trimmed


def _collect_summary_text(summary: Optional[Summary]) -> str:
    if summary is None:
        return ""
    parts: Iterable[Optional[str]] = (
        summary.insight,
        summary.what,
        summary.why,
        summary.how,
        summary.who,
        summary.when,
        summary.where,
    )
    return " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())


def _derive_sentiment(filing: Filing, summary: Optional[Summary]) -> Tuple[str, str, float, str]:
    if filing.analysis_status.upper() != "ANALYZED":
        return ("neutral", "분석이 아직 진행 중입니다.", 0.0, "pending")

    # 1) LLM summary sentiment 우선
    if summary and summary.sentiment_label:
        label = summary.sentiment_label.strip().lower()
        if label in SUMMARY_SENTIMENT_LABELS:
            reason = summary.sentiment_reason or "요약 모델이 공시 내용을 검토한 결과예요."
            score = 1.0 if label == "positive" else (-1.0 if label == "negative" else 0.0)
            return (label, reason, score, "summary")

    # 2) 카테고리 기반
    category_label = _normalize_category_label(filing.category)
    if category_label in POSITIVE_CATEGORIES:
        return ("positive", f"{category_label} 관련 공시로 분류되었습니다.", 0.5, "category")
    if category_label in NEGATIVE_CATEGORIES:
        return ("negative", f"{category_label} 관련 공시로 분류되었습니다. 주의가 필요합니다.", -0.5, "category")

    # 3) 키워드 기반
    text = _collect_summary_text(summary)
    if text:
        score_val = 0
        matched_positive = [kw for kw in POSITIVE_KEYWORDS if kw in text]
        matched_negative = [kw for kw in NEGATIVE_KEYWORDS if kw in text]
        score_val += len(matched_positive)
        score_val -= len(matched_negative)
        if score_val > 0:
            reason = ", ".join(matched_positive) if matched_positive else "긍정 키워드 발견"
            return ("positive", f"요약 본문에서 긍정 키워드가 확인되었습니다 ({reason}).", 0.3, "keywords")
        if score_val < 0:
            reason = ", ".join(matched_negative) if matched_negative else "부정 키워드 발견"
            return ("negative", f"요약 본문에서 부정 키워드가 확인되었습니다 ({reason}).", -0.3, "keywords")

    return ("neutral", "특별한 경고나 기회 요인이 감지되지 않았습니다.", 0.0, "neutral-default")


def _highlight_reason(
    category_label: Optional[str],
    sentiment: str,
    *,
    weight: float,
    recency_days: Optional[float] = None,
    sentiment_reason: Optional[str] = None,
    impact_score: Optional[float] = None,
    novelty_score: Optional[float] = None,
) -> str:
    parts: list[str] = []
    if category_label:
        parts.append(category_label)
    if sentiment and sentiment != "neutral":
        parts.append("긍정" if sentiment == "positive" else "부정")
    if recency_days is not None:
        parts.append(f"{recency_days:.1f}일 이내")
    parts.append(f"가중치 {weight:.2f}")
    if impact_score and impact_score > 0:
        parts.append(f"규모 가점 {impact_score:.2f}")
    if novelty_score and novelty_score > 0:
        parts.append(f"희소성 가점 {novelty_score:.2f}")
    if sentiment_reason:
        parts.append(sentiment_reason)
    return " · ".join(parts)


def _extract_amount_score(text: str) -> Tuple[float, Optional[float]]:
    """Rudimentary impact score: find largest amount in summary text (조/억 단위)."""
    if not text:
        return 0.0, None
    import re

    matches = re.findall(_AMOUNT_PATTERN, text)
    if not matches:
        return 0.0, None
    max_krw = 0.0
    for value, unit in matches:
        try:
            num = float(value)
        except ValueError:
            continue
        multiplier = 1_000_000_000_000 if unit == "조" else 100_000_000
        max_krw = max(max_krw, num * multiplier)
    if max_krw <= 0:
        return 0.0, None
    # Scale: <1e10 -> 0.1, 1e10~1e11 ->0.3, 1e11~1e12 ->0.6, >1e12 ->1.0
    if max_krw >= 1e12:
        score = 1.0
    elif max_krw >= 1e11:
        score = 0.6
    elif max_krw >= 1e10:
        score = 0.3
    else:
        score = 0.1
    return score, max_krw


def _normalize_xml_entries(filing: Filing) -> List[Dict[str, Any]]:
    source_files = filing.source_files or {}
    xml_entries = source_files.get("xml") if isinstance(source_files, dict) else None
    if not xml_entries:
        return []

    normalized: List[Dict[str, Any]] = []
    for entry in xml_entries:
        if isinstance(entry, str):
            normalized.append({"path": entry})
        elif isinstance(entry, dict):
            normalized.append(
                {
                    "path": entry.get("path"),
                    "object": entry.get("object") or entry.get("minio_object"),
                    "url": entry.get("url"),
                    "name": entry.get("name"),
                }
            )
    return normalized


@router.post("/upload", response_model=FilingBriefResponse)
def upload_filing(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a PDF filing and enqueue asynchronous processing."""
    upload_dir = Path("uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(file.filename or "").suffix or ".pdf"
    unique_name = f"{uuid.uuid4()}{extension}"
    file_path = upload_dir / unique_name

    with file_path.open("wb") as buffer:
        buffer.write(file.file.read())

    new_filing = Filing(
        id=uuid.uuid4(),
        file_name=file.filename,
        file_path=str(file_path),
        status="PENDING",
        analysis_status="PENDING",
        source_files={"pdf": str(file_path)},
    )
    db.add(new_filing)
    db.commit()
    db.refresh(new_filing)

    filing_jobs.enqueue_process_filing(str(new_filing.id))
    return new_filing


@router.post("/{filing_id}/fetch", response_model=FilingDetailResponse)
def fetch_filing_content(filing_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Trigger on-demand fetch for a filing that has metadata but no content.
    Useful for 'Smart Backfill' items.
    """
    try:
        updated_filing = filing_fetch_service.fetch_filing_content(db, filing_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    
    # Return detail response
    return FilingDetailResponse.model_validate(updated_filing, from_attributes=True)


@router.get("/", response_model=list[FilingBriefResponse])
def list_filings(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500, description="Maximum number of filings to return."),
    company: str | None = Query(None, description="Filter by company name (exact match)."),
    ticker: str | None = Query(None, description="Filter by ticker symbol."),
    corp_code: str | None = Query(None, description="Filter by OpenDART corp_code."),
    days: int = Query(3, ge=1, le=365, description="Number of days to look back. Defaults to 3 days."),
    start_date: date | None = Query(None, description="Explicit start date (YYYY-MM-DD)."),
    end_date: date | None = Query(None, description="Explicit end date (YYYY-MM-DD)."),
    sentiment: Literal["positive", "negative"] | None = Query(
        None,
        description="Filter by summary sentiment label (positive or negative).",
    ),
    db: Session = Depends(get_db),
):
    """List filings with optional ticker, corp_code, and date range filters."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be earlier than or equal to end_date.")

    query = db.query(Filing)
    
    if company:
        query = query.filter(Filing.company == company)
    if ticker:
        query = query.filter(Filing.ticker == ticker)
    if corp_code:
        query = query.filter(Filing.corp_code == corp_code)

    window_end_date = end_date or datetime.utcnow().date()
    window_start_date = start_date or (window_end_date - timedelta(days=days - 1))

    window_start = datetime.combine(window_start_date, time.min)
    window_end = datetime.combine(window_end_date, time.max)

    query = query.filter(Filing.filed_at.isnot(None))
    if sentiment:
        query = query.join(Summary, Summary.filing_id == Filing.id)
        query = query.filter(Summary.sentiment_label == sentiment)
    query = query.filter(Filing.filed_at >= window_start, Filing.filed_at <= window_end)

    filings = (
        query.order_by(Filing.filed_at.desc(), Filing.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    if not filings:
        return []

    filing_ids = [filing.id for filing in filings]
    summaries = (
        db.query(Summary)
        .filter(Summary.filing_id.in_(filing_ids))
        .all()
    )
    summary_map = {item.filing_id: item for item in summaries}

    responses: list[FilingBriefResponse] = []
    for filing in filings:
        summary = summary_map.get(filing.id)
        sentiment, reason, sentiment_score, sentiment_source = _derive_sentiment(filing, summary)
        base_model = FilingBriefResponse.model_validate(filing, from_attributes=True)
        responses.append(
            base_model.model_copy(
                update={
                    "sentiment": sentiment,
                    "sentiment_reason": reason,
                    "sentiment_score": sentiment_score,
                    "sentiment_source": sentiment_source,
                }
            )
        )
    return responses


@router.get("/highlights", response_model=list[FilingBriefResponse])
def list_highlight_filings(
    days: int = Query(7, ge=1, le=30, description="Look-back window in days."),
    limit: int = Query(30, ge=1, le=100, description="Maximum number of highlighted filings."),
    ticker: str | None = Query(None, description="Filter by ticker."),
    sentiment: Literal["positive", "negative", "neutral"] | None = Query(
        None, description="Optional sentiment filter."
    ),
    start_date: date | None = Query(None, description="Explicit start date (YYYY-MM-DD)."),
    end_date: date | None = Query(None, description="Explicit end date (YYYY-MM-DD)."),
    db: Session = Depends(get_db),
) -> list[FilingBriefResponse]:
    """
    Return a curated set of recent/high-impact filings.

    This is a lightweight filter over the filings table focusing on important categories
    and recent events, sorted by a simple category/sentiment weight then recency.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be earlier than or equal to end_date.")

    query = db.query(Filing)
    if ticker:
        query = query.filter(Filing.ticker == ticker)

    window_end_date = end_date or datetime.utcnow().date()
    window_start_date = start_date or (window_end_date - timedelta(days=days - 1))
    window_start = datetime.combine(window_start_date, time.min)
    window_end = datetime.combine(window_end_date, time.max)

    query = query.filter(Filing.filed_at.isnot(None))
    query = query.filter(Filing.filed_at >= window_start, Filing.filed_at <= window_end)

    candidates: list[Filing] = (
        query.order_by(Filing.filed_at.desc(), Filing.created_at.desc())
        .limit(max(limit * 4, limit))
        .all()
    )

    if not candidates:
        return []

    filing_ids = [filing.id for filing in candidates]
    summaries = db.query(Summary).filter(Summary.filing_id.in_(filing_ids)).all()
    summary_map = {item.filing_id: item for item in summaries}

    # Novelty: count same ticker/category in last 90 days for quick rarity boost
    novelty_window_start = datetime.combine(window_end_date - timedelta(days=89), time.min)
    novelty_counts: Dict[Tuple[str, str], int] = {}
    rows = (
        db.query(Filing.ticker, Filing.category, func.count(Filing.id))
        .filter(Filing.filed_at.isnot(None))
        .filter(Filing.filed_at >= novelty_window_start, Filing.filed_at <= window_end)
        .group_by(Filing.ticker, Filing.category)
        .all()
    )
    for ticker_val, category_val, count_val in rows:
        key = (ticker_val or "", _normalize_category_label(category_val))
        novelty_counts[key] = int(count_val or 0)

    ranked: list[tuple[float, FilingBriefResponse, datetime]] = []
    seen_tickers: set[str] = set()

    for filing in candidates:
        category_label = _normalize_category_label(filing.category)
        if category_label and category_label not in HIGHLIGHT_CATEGORY_SET:
            continue

        summary = summary_map.get(filing.id)
        derived_sentiment, reason, sentiment_score, sentiment_source = _derive_sentiment(filing, summary)
        if sentiment and derived_sentiment != sentiment:
            continue

        base_model = FilingBriefResponse.model_validate(filing, from_attributes=True)
        payload = base_model.model_copy(
            update={
                "sentiment": derived_sentiment,
                "sentiment_reason": reason,
                "insight_score": None,
                "highlight_reason": None,
                "highlight_flags": None,
                "sentiment_score": sentiment_score,
                "sentiment_source": sentiment_source,
            }
        )

        weight = CATEGORY_WEIGHTS.get(category_label or "", 0.2)
        if derived_sentiment == "negative":
            weight += 0.05
        elif derived_sentiment == "positive":
            weight += 0.02

        # Impact score from summary text amount
        summary_text = _collect_summary_text(summary)
        impact_score, impact_amount = _extract_amount_score(summary_text)
        weight += impact_score * 0.1

        # Novelty score: rarer category/ticker in recent 90 days gets boost
        novelty_key = (filing.ticker or "", category_label or "")
        novelty_count = novelty_counts.get(novelty_key, 0)
        novelty_score = 0.0
        if novelty_count == 0:
            novelty_score = 0.1
        elif novelty_count <= 3:
            novelty_score = 0.05
        weight += novelty_score

        filed_at = filing.filed_at or filing.created_at or datetime.min
        days_delta: Optional[float] = None
        if filed_at and filed_at != datetime.min:
            days_delta = (datetime.utcnow() - filed_at).total_seconds() / 86400.0
            # 최근일수록 약간 가중치
            if days_delta <= 7:
                weight += max(0.0, (7 - days_delta) / 7) * 0.08

        ticker_key = filing.ticker or filing.corp_code or filing.company
        if ticker_key and ticker_key in seen_tickers:
            continue
        if ticker_key:
            seen_tickers.add(ticker_key)

        payload.highlight_reason = _highlight_reason(
            category_label,
            derived_sentiment,
            weight=weight,
            recency_days=days_delta,
            sentiment_reason=reason,
            impact_score=impact_score,
            novelty_score=novelty_score,
        )
        payload.insight_score = round(weight, 3)
        payload.highlight_flags = {
            "category": category_label,
            "sentiment": derived_sentiment,
            "sentiment_score": sentiment_score,
            "sentiment_source": sentiment_source,
            "weight": weight,
            "recency_days": days_delta,
            "impact_score": impact_score,
            "impact_amount_krw": impact_amount,
            "novelty_count_90d": novelty_count,
            "novelty_score": novelty_score,
        }

        ranked.append((weight, payload, filed_at))

    ranked.sort(key=lambda item: (item[0], item[2]), reverse=True)
    return [entry[1] for entry in ranked[:limit]]


@router.get("/{filing_id}", response_model=FilingDetailResponse)
def get_filing_details(filing_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return filing metadata, summary, and extracted facts."""
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    facts = db.query(ExtractedFact).filter(ExtractedFact.filing_id == filing_id).all()

    summary_payload = None
    if summary:
        summary_payload = SummaryResponse.model_validate(summary, from_attributes=True)
        summary_payload.sentiment = summary.sentiment_label
        summary_payload.sentiment_label = summary.sentiment_label
        summary_payload.sentiment_reason = summary.sentiment_reason
    facts_payload = [
        FactResponse.model_validate(fact, from_attributes=True) for fact in facts
    ]

    sentiment, reason, sentiment_score, sentiment_source = _derive_sentiment(filing, summary)

    filing_payload = FilingDetailResponse.model_validate(filing, from_attributes=True)
    return filing_payload.model_copy(
        update={
            "summary": summary_payload,
            "facts": facts_payload,
            "sentiment": sentiment,
            "sentiment_reason": reason,
            "sentiment_score": sentiment_score,
            "sentiment_source": sentiment_source,
        }
    )


def _load_xml_document(entry: Dict[str, Any], temp_dir: Path, filing_id: uuid.UUID) -> Optional[FilingXmlDocument]:
    candidate_path = entry.get("path")
    object_name = entry.get("object")
    remote_url = entry.get("url")
    explicit_name = entry.get("name")

    if candidate_path:
        path_obj = Path(candidate_path)
        if path_obj.is_file():
            try:
                content = path_obj.read_text(encoding="utf-8", errors="ignore")
                return FilingXmlDocument(
                    name=explicit_name or path_obj.name,
                    path=str(path_obj),
                    content=content,
                )
            except OSError as exc:
                logger.warning("Failed to read XML file for filing %s (%s): %s", filing_id, candidate_path, exc)

    if object_name and storage_service.is_enabled():
        target_path = temp_dir / Path(object_name).name
        downloaded = storage_service.download_file(object_name, str(target_path))
        if downloaded:
            try:
                path_obj = Path(downloaded)
                content = path_obj.read_text(encoding="utf-8", errors="ignore")
                return FilingXmlDocument(
                    name=explicit_name or path_obj.name,
                    path=object_name,
                    content=content,
                )
            except OSError as exc:
                logger.warning("Failed to read downloaded XML for filing %s (%s): %s", filing_id, object_name, exc)

    if remote_url and isinstance(remote_url, str) and remote_url.startswith("http"):
        try:
            response = httpx.get(remote_url, timeout=15.0)
            response.raise_for_status()
            parsed = urlparse(remote_url)
            filename = explicit_name or Path(parsed.path).name or f"{filing_id}.xml"
            return FilingXmlDocument(
                name=filename,
                path=remote_url,
                content=response.text,
            )
        except Exception as exc:
            logger.warning("Failed to fetch XML via URL for filing %s (%s): %s", filing_id, remote_url, exc)

    return None


@router.get("/{filing_id}/xml", response_model=FilingXmlResponse)
def get_filing_xml_documents(filing_id: uuid.UUID, db: Session = Depends(get_db)) -> FilingXmlResponse:
    """Return raw XML sources associated with a filing for highlight rendering."""
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    xml_entries = _normalize_xml_entries(filing)
    if not xml_entries:
        raise HTTPException(status_code=404, detail="No XML source files available for this filing.")

    documents: list[FilingXmlDocument] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir)
        for entry in xml_entries:
            document = _load_xml_document(entry, cache_dir, filing.id)
            if document:
                documents.append(document)

    if not documents:
        raise HTTPException(status_code=500, detail="XML sources are recorded but cannot be accessed.")

    return FilingXmlResponse(filing_id=filing.id, documents=documents)
