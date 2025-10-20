import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models.fact import ExtractedFact
from models.filing import Filing
from models.summary import Summary
from parse.tasks import process_filing
from schemas.api.filing import (
    FactResponse,
    FilingBriefResponse,
    FilingDetailResponse,
    SummaryResponse,
)

router = APIRouter(prefix="/filings", tags=["Filings"])


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
    return filings


@router.get("/{filing_id}", response_model=FilingDetailResponse)
def get_filing_details(filing_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return filing metadata, summary, and extracted facts."""
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    facts = db.query(ExtractedFact).filter(ExtractedFact.filing_id == filing_id).all()

    return FilingDetailResponse(
        **filing.__dict__,
        summary=summary,
        facts=facts,
    )
