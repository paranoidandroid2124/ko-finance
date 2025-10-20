from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class FactResponse(BaseModel):
    fact_type: str
    value: str
    unit: Optional[str] = None
    currency: Optional[str] = None
    anchor_page: Optional[int] = None
    anchor_quote: Optional[str] = None
    anchor: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None

    class Config:
        from_attributes = True


class SummaryResponse(BaseModel):
    who: Optional[str] = None
    what: Optional[str] = None
    when: Optional[str] = None
    where: Optional[str] = None
    how: Optional[str] = None
    why: Optional[str] = None
    insight: Optional[str] = None
    confidence_score: Optional[float] = None

    class Config:
        from_attributes = True


class FilingBriefResponse(BaseModel):
    id: uuid.UUID
    corp_code: Optional[str] = None
    corp_name: Optional[str] = None
    ticker: Optional[str] = None
    report_name: Optional[str] = None
    filed_at: Optional[datetime] = None
    status: str
    analysis_status: str
    category: Optional[str] = None
    category_confidence: Optional[float] = None

    class Config:
        from_attributes = True


class FilingDetailResponse(FilingBriefResponse):
    urls: Optional[Dict[str, Any]] = None
    source_files: Optional[Dict[str, Any]] = None
    file_name: Optional[str] = None
    raw_md: Optional[str] = None
    notes: Optional[str] = None
    summary: Optional[SummaryResponse] = None
    facts: List[FactResponse] = []
