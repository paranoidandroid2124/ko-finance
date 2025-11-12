"""API response schemas for Market Mood endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class NewsSignalResponse(BaseModel):
    """Serialized news signal delivered through the public API."""

    id: uuid.UUID
    ticker: Optional[str] = None
    source: str
    headline: str
    url: str
    published_at: datetime
    sentiment: Optional[float] = None
    source_reliability: Optional[float] = Field(
        None, description="Heuristic reliability score (0~1)"
    )
    topics: List[str] = Field(default_factory=list)
    license_type: Optional[str] = None
    license_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TopicStatResponse(BaseModel):
    """Topic frequency included in an observation window."""

    topic: str
    count: int


class NewsObservationResponse(BaseModel):
    """Aggregated Market Mood observation for a time window."""

    id: uuid.UUID
    window_start: datetime
    window_end: datetime
    article_count: int
    positive_count: int
    neutral_count: int
    negative_count: int
    avg_sentiment: Optional[float] = None
    min_sentiment: Optional[float] = None
    max_sentiment: Optional[float] = None
    top_topics: List[TopicStatResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NewsTopicInsight(BaseModel):
    name: str
    change: str
    sentiment: str
    topArticleId: uuid.UUID | None = None
    topArticleTitle: str | None = None
    topArticleUrl: str | None = None
    topArticleSource: str | None = None
    topArticlePublishedAt: str | None = None


class NewsListItem(BaseModel):
    id: uuid.UUID
    title: str
    sentiment: str
    source: str
    publishedAt: str
    sector: str
    sentimentScore: Optional[float] = None
    publishedAtIso: str
    url: str
    summary: Optional[str] = None
    source_reliability: Optional[float] = None
    licenseType: Optional[str] = None
    licenseUrl: Optional[str] = None


class NewsInsightsResponse(BaseModel):
    news: List[NewsListItem]
    topics: List[NewsTopicInsight]

