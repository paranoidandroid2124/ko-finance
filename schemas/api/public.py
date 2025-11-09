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
