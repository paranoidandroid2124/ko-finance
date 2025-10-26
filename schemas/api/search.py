"""Pydantic schemas for aggregated search responses."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


ResultType = Literal["filing", "news", "table", "chart"]


class SearchResultActions(BaseModel):
    compareLocked: Optional[bool] = None
    alertLocked: Optional[bool] = None
    exportLocked: Optional[bool] = None


class SearchEvidenceCounts(BaseModel):
    filings: Optional[int] = None
    news: Optional[int] = None
    tables: Optional[int] = None
    charts: Optional[int] = None


class SearchResult(BaseModel):
    id: str
    type: ResultType
    title: str
    category: str
    filedAt: Optional[str] = None
    latestIngestedAt: Optional[str] = None
    sourceReliability: Optional[float] = None
    evidenceCounts: Optional[SearchEvidenceCounts] = None
    actions: Optional[SearchResultActions] = None


class SearchTotals(BaseModel):
    filing: int = 0
    news: int = 0
    table: int = 0
    chart: int = 0


class SearchResponse(BaseModel):
    query: str
    total: int
    totals: SearchTotals
    results: list[SearchResult]
