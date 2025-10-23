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

POSITIVE_CATEGORIES = {
    "buyback",
    "large_contract",
    "capital_increase",
}
NEGATIVE_CATEGORIES = {
    "litigation",
    "correction",
    "insider_ownership",
    "audit_opinion",
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
}


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
        return ("neutral", "Analysis is still running.")

    category = (filing.category or "").lower().strip()
    if category in POSITIVE_CATEGORIES:
        return ("positive", f"LLM classification detected the '{category}' category.")
    if category in NEGATIVE_CATEGORIES:
        return ("negative", f"LLM classification detected the '{category}' category.")

    text = _collect_summary_text(summary)
    if text:
        score = 0
        matched_positive = [kw for kw in POSITIVE_KEYWORDS if kw in text]
        matched_negative = [kw for kw in NEGATIVE_KEYWORDS if kw in text]
        score += len(matched_positive)
        score -= len(matched_negative)
        if score > 0:
            reason = ", ".join(matched_positive) if matched_positive else "positive keywords detected"
            return ("positive", f"Positive keywords detected in the summary ({reason}).")
        if score < 0:
            reason = ", ".join(matched_negative) if matched_negative else "negative keywords detected"
            return ("negative", f"Negative keywords detected in the summary ({reason}).")

    return ("neutral", "No notable warning or opportunity detected.")


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
