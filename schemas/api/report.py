"""Pydantic schemas for report APIs."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ReportSourceSchema(BaseModel):
    title: str
    url: str
    date: str


class ReportGenerateRequest(BaseModel):
    ticker: str


class ReportGenerateResponse(BaseModel):
    reportId: Optional[str]
    ticker: str
    content: str
    sources: List[ReportSourceSchema]
    charts: Optional[dict] = None


class ReportExportRequest(BaseModel):
    format: str
    chartImage: Optional[str] = None
    keyStats: Optional[dict] = None


class ReportFeedbackRequest(BaseModel):
    sentiment: str
    category: Optional[str] = None
    comment: Optional[str] = None


class ReportHistoryItem(BaseModel):
    id: str
    ticker: str
    title: Optional[str]
    content: str
    sources: List[ReportSourceSchema]
    createdAt: datetime


class ReportHistoryResponse(BaseModel):
    items: List[ReportHistoryItem]


__all__ = [
    "ReportSourceSchema",
    "ReportGenerateRequest",
    "ReportGenerateResponse",
    "ReportExportRequest",
    "ReportFeedbackRequest",
    "ReportHistoryItem",
    "ReportHistoryResponse",
]
