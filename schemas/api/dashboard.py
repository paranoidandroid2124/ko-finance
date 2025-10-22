"""Pydantic schemas for dashboard overview responses."""

from __future__ import annotations

from typing import Literal

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


class DashboardNewsItem(BaseModel):
    id: str
    title: str
    sentiment: Literal["positive", "negative", "neutral"]
    source: str
    publishedAt: str


class DashboardOverviewResponse(BaseModel):
    metrics: list[DashboardMetric]
    alerts: list[DashboardAlert]
    news: list[DashboardNewsItem]


class FilingTrendPoint(BaseModel):
    date: str
    count: int
    rolling_average: float


class FilingTrendResponse(BaseModel):
    points: list[FilingTrendPoint]
