import uuid
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from core.logging import get_logger
from database import get_db
from models.fact import ExtractedFact
from models.filing import Filing
from models.summary import Summary
from parse.tasks import process_filing
from schemas.api.filing import (
    FactResponse,
    FilingBriefResponse,
    FilingDetailResponse,
    FilingXmlDocument,
    FilingXmlResponse,
    SummaryResponse,
)
from services import minio_service

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


def _derive_sentiment(filing: Filing, summary: Optional[Summary]) -> Tuple[str, str]:
    if filing.analysis_status.upper() != "ANALYZED":
        return ("neutral", "분석이 아직 진행 중입니다.")

    category_label = _normalize_category_label(filing.category)
    if category_label in POSITIVE_CATEGORIES:
        return ("positive", f"{category_label} 관련 공시로 분류되었습니다.")
    if category_label in NEGATIVE_CATEGORIES:
        return ("negative", f"{category_label} 관련 공시로 분류되었습니다. 주의가 필요합니다.")

    text = _collect_summary_text(summary)
    if text:
        score = 0
        matched_positive = [kw for kw in POSITIVE_KEYWORDS if kw in text]
        matched_negative = [kw for kw in NEGATIVE_KEYWORDS if kw in text]
        score += len(matched_positive)
        score -= len(matched_negative)
        if score > 0:
            reason = ", ".join(matched_positive) if matched_positive else "긍정 키워드 발견"
            return ("positive", f"요약 본문에서 긍정 키워드가 확인되었습니다 ({reason}).")
        if score < 0:
            reason = ", ".join(matched_negative) if matched_negative else "부정 키워드 발견"
            return ("negative", f"요약 본문에서 부정 키워드가 확인되었습니다 ({reason}).")

    return ("neutral", "특별한 경고나 기회 요인이 감지되지 않았습니다.")


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

    process_filing.delay(str(new_filing.id))
    return new_filing


@router.get("/", response_model=list[FilingBriefResponse])
def list_filings(
    skip: int = 0,
    limit: int = 10,
    ticker: str | None = Query(None, description="Filter by ticker symbol"),
    db: Session = Depends(get_db),
):
    """List filings with optional ticker filter."""
    query = db.query(Filing)
    if ticker:
        query = query.filter(Filing.ticker == ticker)
    filings = query.order_by(Filing.filed_at.desc()).offset(skip).limit(limit).all()

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
        sentiment, reason = _derive_sentiment(filing, summary)
        base_model = FilingBriefResponse.model_validate(filing, from_attributes=True)
        responses.append(
            base_model.model_copy(
                update={
                    "sentiment": sentiment,
                    "sentiment_reason": reason,
                }
            )
        )
    return responses


@router.get("/{filing_id}", response_model=FilingDetailResponse)
def get_filing_details(filing_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return filing metadata, summary, and extracted facts."""
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    facts = db.query(ExtractedFact).filter(ExtractedFact.filing_id == filing_id).all()

    summary_payload = (
        SummaryResponse.model_validate(summary, from_attributes=True) if summary else None
    )
    facts_payload = [
        FactResponse.model_validate(fact, from_attributes=True) for fact in facts
    ]

    sentiment, reason = _derive_sentiment(filing, summary)

    filing_payload = FilingDetailResponse.model_validate(filing, from_attributes=True)
    return filing_payload.model_copy(
        update={
            "summary": summary_payload,
            "facts": facts_payload,
            "sentiment": sentiment,
            "sentiment_reason": reason,
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

    if object_name and minio_service.is_enabled():
        target_path = temp_dir / Path(object_name).name
        downloaded = minio_service.download_file(object_name, str(target_path))
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
