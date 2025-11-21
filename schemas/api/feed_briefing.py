from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from .feed import FeedItemResponse


class FeedBriefing(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    ticker: Optional[str] = None
    count: int
    items: List[FeedItemResponse]


class FeedBriefingListResponse(BaseModel):
    items: List[FeedBriefing]


__all__ = ["FeedBriefing", "FeedBriefingListResponse"]
