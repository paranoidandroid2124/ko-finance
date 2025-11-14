"""Pydantic schemas for dashboard overview responses."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class DashboardMetric(BaseModel):
    title: str
    value: str
    delta: str
    trend: Literal["up", "down", "flat"]
    description: str


class DashboardAlert(BaseModel):
    id: str
    title: str
    body: str
    timestamp: str
    tone: Literal["positive", "negative", "neutral", "warning"]
    targetUrl: str | None = None


class DashboardNewsItem(BaseModel):
    id: str
    title: str
    sentiment: Literal["positive", "negative", "neutral"]
    source: str
    publishedAt: str
    url: str


class DashboardOverviewResponse(BaseModel):
    metrics: list[DashboardMetric]
    alerts: list[DashboardAlert]
    news: list[DashboardNewsItem]
    watchlists: list["DashboardWatchlistSummary"] = []
    events: list["DashboardEventItem"] = []
    quickLinks: list["DashboardQuickLink"] = []
    sectorHeatmapAsOf: Optional[str] = None
    sectorHeatmapWindow: Optional[int] = None


class DashboardWatchlistSummary(BaseModel):
    ruleId: str
    name: str
    eventCount: int
    tickers: list[str] = []
    channels: list[str] = []
    lastTriggeredAt: Optional[str] = None
    lastHeadline: Optional[str] = None
    detailUrl: Optional[str] = None


class DashboardEventItem(BaseModel):
    id: str
    ticker: Optional[str] = None
    corpName: Optional[str] = None
    title: str
    eventType: Optional[str] = None
    filedAt: Optional[str] = None
    severity: Literal["info", "warning", "critical", "neutral"] = "info"
    targetUrl: Optional[str] = None


class DashboardQuickLink(BaseModel):
    label: str
    href: str
    type: Literal["search", "company", "board"]


class FilingTrendPoint(BaseModel):
    date: str
    count: int
    rolling_average: float


class FilingTrendResponse(BaseModel):
    points: list[FilingTrendPoint]
