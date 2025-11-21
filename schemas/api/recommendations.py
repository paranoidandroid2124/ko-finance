from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    question: str = Field(..., description="User-ready starter question text.")
    source: str = Field(..., description="origin of recommendation (filing/profile/default)")
    ticker: Optional[str] = Field(None, description="Matched ticker, if any")
    corpName: Optional[str] = Field(None, description="Company name, if any")
    filedAt: Optional[str] = Field(None, description="Filing timestamp ISO")
    filingId: Optional[str] = Field(None, description="Filing UUID")


class RecommendationsResponse(BaseModel):
    items: List[RecommendationItem]


__all__ = ["RecommendationItem", "RecommendationsResponse"]
