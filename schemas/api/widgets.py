"""Widget payload schemas for chat attachments."""

from __future__ import annotations

from typing import List, Literal, Union

from pydantic import BaseModel, Field


class LineChartWidget(BaseModel):
    type: Literal["line"]
    title: str | None = Field(default=None, description="Optional heading for the chart.")
    label: str = Field(description="Chart title or label (e.g., ticker name).")
    unit: str | None = Field(default=None, description="Optional unit label, e.g., KRW.")
    description: str | None = Field(default=None, description="Optional helper text for the chart.")
    data: List[dict] = Field(description="Time series datapoints, e.g., [{'date': 'YYYY-MM-DD', 'price': 12345.0}].")


class FinancialTableWidget(BaseModel):
    type: Literal["financials"]
    title: str | None = Field(default=None, description="Optional heading for the table.")
    description: str | None = Field(default=None, description="Optional helper text for the table.")
    headers: List[str] = Field(description="Table headers, e.g., ['항목', '값'].")
    rows: List[List[str]] = Field(
        description="2D rows matching headers order, e.g., [['매출액', '1,234억'], ...]."
    )


class StatCardWidget(BaseModel):
    type: Literal["summary"]
    title: str = Field(description="Label for the stat card.")
    value: str
    description: str | None = Field(default=None, description="Additional context for the value.")


WidgetAttachment = Union[LineChartWidget, FinancialTableWidget, StatCardWidget]

__all__ = [
    "LineChartPoint",
    "LineChartWidget",
    "FinancialTableWidget",
    "StatCardWidget",
    "WidgetAttachment",
]
