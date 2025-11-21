from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class FeedItemResponse(BaseModel):
    id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    ticker: Optional[str] = None
    type: Optional[str] = None  # news | filing | alert
    targetUrl: Optional[str] = None
    createdAt: Optional[str] = None
    status: Optional[str] = None  # unread | read | dismissed


class FeedListResponse(BaseModel):
    items: List[FeedItemResponse]


__all__ = ["FeedItemResponse", "FeedListResponse"]
