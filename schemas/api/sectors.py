"""API schemas for sector-level sentiment endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SectorRef(BaseModel):
    id: int
    slug: str
    name: str


class SectorTopArticle(BaseModel):
    id: uuid.UUID
    title: str
    summary: Optional[str] = None
    url: str
    targetUrl: Optional[str] = None
    tone: Optional[float] = None
    publishedAt: datetime


class SectorSignalPoint(BaseModel):
    sector: SectorRef
    sentimentZ: float
    volumeZ: float
    deltaSentiment7d: Optional[float] = None
    sentimentMean: Optional[float] = None
    volumeSum: Optional[int] = None
    topArticle: Optional[SectorTopArticle] = None


class SectorSignalsResponse(BaseModel):
    asOf: date
    windowDays: int
    points: List[SectorSignalPoint] = Field(default_factory=list)


class SectorTimeseriesPoint(BaseModel):
    date: date
    sentMean: Optional[float] = None
    volume: int


class SectorCurrentSnapshot(BaseModel):
    sentZ7d: Optional[float] = None
    delta7d: Optional[float] = None


class SectorTimeseriesResponse(BaseModel):
    sector: SectorRef
    series: List[SectorTimeseriesPoint] = Field(default_factory=list)
    current: SectorCurrentSnapshot


class SectorTopArticlesResponse(BaseModel):
    sector: SectorRef
    items: List[SectorTopArticle] = Field(default_factory=list)
