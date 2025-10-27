"\"\"\"Pydantic schemas for company snapshot endpoints.\"\"\""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class FilingHeadline(BaseModel):
    """Headline information for the latest filing."""

    receipt_no: Optional[str] = Field(None, description="DART receipt number")
    report_name: Optional[str] = Field(None, description="Filing report name")
    title: Optional[str] = Field(None, description="Filing title")
    filed_at: Optional[datetime] = Field(None, description="Filed at timestamp")
    viewer_url: Optional[str] = Field(None, description="Direct viewer URL")


class SummaryBlock(BaseModel):
    """Structured summary text for the latest filing."""

    insight: Optional[str] = None
    who: Optional[str] = None
    what: Optional[str] = None
    when: Optional[str] = None
    where: Optional[str] = None
    why: Optional[str] = None
    how: Optional[str] = None


class KeyMetric(BaseModel):
    """Key financial metric extracted from DART summaries."""

    metric_code: str = Field(..., description="Metric identifier (account id)")
    label: str = Field(..., description="Metric label")
    value: Optional[float] = Field(None, description="Numeric value (unitless)")
    unit: Optional[str] = Field(None, description="Reporting unit")
    fiscal_year: Optional[int] = Field(None, description="Fiscal year")
    fiscal_period: Optional[str] = Field(None, description="Fiscal period label (FY/Q1/Q2/Q3)")


class EventItem(BaseModel):
    """Major event extracted from DART DE005."""

    id: uuid.UUID
    event_type: str
    event_name: Optional[str] = None
    event_date: Optional[date] = None
    resolution_date: Optional[date] = None
    report_name: Optional[str] = None
    derived_metrics: dict = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class TopicWeight(BaseModel):
    topic: str
    count: int
    weight: float


class NewsWindowInsight(BaseModel):
    """Aggregated news metrics for dashboard cards."""

    scope: str
    ticker: Optional[str] = None
    window_days: int
    computed_for: datetime

    article_count: int
    avg_sentiment: Optional[float] = None
    sentiment_z: Optional[float] = None
    novelty_kl: Optional[float] = None
    topic_shift: Optional[float] = None
    domestic_ratio: Optional[float] = None
    domain_diversity: Optional[float] = None
    top_topics: List[TopicWeight] = Field(default_factory=list)
    source_reliability: Optional[float] = Field(
        None, description="Heuristic reliability score for the aggregated window"
    )

    model_config = ConfigDict(from_attributes=True)


class CompanySnapshotResponse(BaseModel):
    """Complete snapshot payload for company overview."""

    corp_code: Optional[str] = None
    ticker: Optional[str] = None
    corp_name: Optional[str] = None

    latest_filing: Optional[FilingHeadline] = None
    summary: Optional[SummaryBlock] = None
    key_metrics: List[KeyMetric] = Field(default_factory=list)
    major_events: List[EventItem] = Field(default_factory=list)
    news_signals: List[NewsWindowInsight] = Field(default_factory=list)


class CompanySearchResult(BaseModel):
    """Lightweight metadata for search/autocomplete."""

    corp_code: Optional[str] = Field(None, description="DART corporation code")
    ticker: Optional[str] = Field(None, description="Equity ticker symbol")
    corp_name: Optional[str] = Field(None, description="Legal corporation name")
    latest_report_name: Optional[str] = Field(None, description="Most recent report name")
    latest_filed_at: Optional[datetime] = Field(None, description="Most recent filing timestamp")
    highlight: Optional[str] = Field(None, description="Contextual reason for suggestion")

    model_config = ConfigDict(from_attributes=True)


class CompanySuggestions(BaseModel):
    """Aggregated suggestions for landing page."""

    recent_filings: List[CompanySearchResult] = Field(default_factory=list)
    trending_news: List[CompanySearchResult] = Field(default_factory=list)


class TimelinePoint(BaseModel):
    date: date
    sentiment_z: Optional[float] = None
    price_close: Optional[float] = None
    volume: Optional[float] = None
    event_type: Optional[str] = None


class TimelineResponse(BaseModel):
    window_days: int
    total_points: int
    downsampled_points: int
    points: List[TimelinePoint] = Field(default_factory=list)
