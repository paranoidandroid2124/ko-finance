"""Pydantic schemas for public/unauthenticated preview APIs."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PublicFiling(BaseModel):
    id: str
    corpName: Optional[str] = None
    reportName: Optional[str] = None
    category: Optional[str] = None
    market: Optional[str] = None
    filedAt: Optional[datetime] = None
    highlight: Optional[str] = None
    targetUrl: Optional[str] = Field(default=None, description="Dashboard deep link for the filing.")


class PublicFilingsResponse(BaseModel):
    filings: List[PublicFiling]


class PublicChatRequest(BaseModel):
    question: str = Field(..., min_length=4, max_length=400, description="사용자가 입력한 미리보기 질문.")


class PublicChatSource(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    filedAt: Optional[datetime] = None
    targetUrl: Optional[str] = None


class PublicChatResponse(BaseModel):
    answer: str
    sources: List[PublicChatSource]
    disclaimer: str


class PublicEventShareResponse(BaseModel):
    receiptNo: str
    corpName: Optional[str] = None
    ticker: Optional[str] = None
    reportName: Optional[str] = None
    eventName: Optional[str] = None
    eventType: Optional[str] = None
    filedAt: Optional[datetime] = None
    caar: Optional[float] = Field(default=None, description="CAAR[-2,+5] 혹은 기본 윈도우")
    pValue: Optional[float] = Field(default=None, description="CAAR p-value")
    focusScore: Optional[float] = Field(default=None, description="Focus Score 총점")
    focusDetails: Optional[dict] = Field(default=None, description="Focus Score 서브 점수 원본")
    targetUrl: Optional[str] = Field(default=None, description="대시보드 딥링크 (/filings?receiptNo=)")


__all__ = [
    "PublicFiling",
    "PublicFilingsResponse",
    "PublicChatRequest",
    "PublicChatSource",
    "PublicChatResponse",
    "PublicEventShareResponse",
]
