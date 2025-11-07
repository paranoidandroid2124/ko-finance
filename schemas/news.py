"""Pydantic schemas shared across the Market Mood pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class NewsArticleBase(BaseModel):
    """Common attributes for a news article."""

    ticker: Optional[str] = Field(None, description="Optional equity ticker")
    source: str = Field(..., description="Feed source or publisher name")
    url: str = Field(..., description="Canonical article URL")
    headline: str = Field(..., description="Article headline")
    summary: Optional[str] = Field(None, description="Optional extractive summary")
    published_at: datetime = Field(..., description="Published timestamp")
    license_type: Optional[str] = Field(
        None,
        description="Normalised license label (e.g. KOGL 제1유형)",
    )
    license_url: Optional[str] = Field(
        None,
        description="License reference URL when provided by the source",
    )


class NewsArticleCreate(NewsArticleBase):
    """Payload required when ingesting news content."""

    original_text: str = Field(..., description="Full text used for downstream analysis")


class NewsArticle(NewsArticleBase):
    """News article retrieved via API with computed sentiment."""

    id: uuid.UUID
    sentiment: Optional[float] = Field(None, description="LLM sentiment score (-1.0 ~ 1.0)")
    topics: List[str] = Field(default_factory=list, description="Topical keywords identified by LLM")

    model_config = ConfigDict(from_attributes=True)


class TopicStat(BaseModel):
    """Topic frequency statistic."""

    topic: str
    count: int


class NewsObservation(BaseModel):
    """Aggregate metrics for a Market Mood observation window."""

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
    top_topics: List[TopicStat] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
