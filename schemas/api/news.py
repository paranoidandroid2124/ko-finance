"""API response schemas for Market Mood endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class NewsSignalResponse(BaseModel):
    """Serialized news signal delivered through the public API."""

    id: uuid.UUID
    ticker: Optional[str] = None
    source: str
    headline: str
    url: str
    published_at: datetime
    sentiment: Optional[float] = None
    topics: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True

