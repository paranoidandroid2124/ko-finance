"""Pydantic schemas for watchlist/sector board API responses."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class BoardSummarySchema(BaseModel):
    id: str = Field(..., description="Board identifier (maps to alert rule id).")
    name: str = Field(..., description="Display name for the board.")
    type: Literal["watchlist", "sector", "theme"] = Field(..., description="Board classification.")
    description: Optional[str] = Field(default=None, description="Optional board description.")
    tickers: list[str] = Field(default_factory=list, description="Tickers included in the board.")
    eventCount: int = Field(default=0, description="Number of recent events observed for this board.")
    recentAlerts: int = Field(default=0, description="Recent alert deliveries associated with this board.")
    channels: list[str] = Field(default_factory=list, description="Delivery channels tied to the rule.")
    updatedAt: Optional[str] = Field(default=None, description="ISO timestamp of the latest alert.")


class BoardEntrySchema(BaseModel):
    ticker: str
    corpName: Optional[str] = None
    sector: Optional[str] = None
    eventCount: int = 0
    lastHeadline: Optional[str] = None
    lastEventAt: Optional[str] = None
    sentiment: Optional[float] = None
    alertStatus: Optional[str] = None
    targetUrl: Optional[str] = None


class BoardEventSchema(BaseModel):
    id: str
    headline: str
    summary: Optional[str] = None
    channel: Optional[str] = None
    sentiment: Optional[float] = None
    deliveredAt: Optional[str] = None
    url: Optional[str] = None


class BoardListResponse(BaseModel):
    boards: list[BoardSummarySchema] = Field(default_factory=list)


class BoardDetailResponse(BaseModel):
    board: BoardSummarySchema
    entries: list[BoardEntrySchema] = Field(default_factory=list)
    timeline: list[BoardEventSchema] = Field(default_factory=list)
