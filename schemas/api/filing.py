from pydantic import BaseModel, Field
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
    sentiment: str = Field("neutral", description="Derived sentiment label based on classification/summary")
    sentiment_reason: Optional[str] = Field(None, description="Short explanation of the sentiment label")

    class Config:
        from_attributes = True


class FilingDetailResponse(FilingBriefResponse):
    urls: Optional[Dict[str, Any]] = None
    source_files: Optional[Dict[str, Any]] = None
    file_name: Optional[str] = None
    raw_md: Optional[str] = None
    notes: Optional[str] = None
    summary: Optional[SummaryResponse] = None
    facts: List[FactResponse] = Field(default_factory=list)


class FilingXmlDocument(BaseModel):
    name: str = Field(..., description="원본 XML 파일 이름")
    path: str = Field(..., description="서버 상의 XML 파일 경로")
    content: str = Field(..., description="XML 파일의 전체 본문 (UTF-8)")


class FilingXmlResponse(BaseModel):
    filing_id: uuid.UUID
    documents: List[FilingXmlDocument] = Field(default_factory=list)
