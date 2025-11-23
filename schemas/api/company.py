"\"\"\"Pydantic schemas for company snapshot endpoints.\"\"\""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class FilingHeadline(BaseModel):
    """Headline information for the latest filing."""

    receipt_no: Optional[str] = Field(None, description="DART receipt number")
    report_name: Optional[str] = Field(None, description="Filing report name")
    title: Optional[str] = Field(None, description="Filing title")
    filed_at: Optional[datetime] = Field(None, description="Filed at timestamp")
    viewer_url: Optional[str] = Field(None, description="Direct viewer URL")


class SummaryBlock(BaseModel):
    """Structured summary text for the latest filing."""

    insight: Optional[str] = None
    who: Optional[str] = None
    what: Optional[str] = None
    when: Optional[str] = None
    where: Optional[str] = None
    why: Optional[str] = None
    how: Optional[str] = None


class CompanyFilingSummary(BaseModel):
    """Compact payload for recent filings shown on the company page."""

    id: uuid.UUID
    receipt_no: Optional[str] = Field(None, description="DART receipt number")
    report_name: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    filed_at: Optional[datetime] = Field(None, serialization_alias="filedAt")
    viewer_url: Optional[str] = None
    summary: Optional[SummaryBlock] = None
    sentiment: Optional[str] = Field(
        None,
        description="Heuristic sentiment label derived from summary/category context.",
    )
    sentiment_reason: Optional[str] = Field(
        None,
        serialization_alias="sentimentReason",
        description="Human-readable explanation for the sentiment label.",
    )

    model_config = ConfigDict(from_attributes=True)


class FinancialValue(BaseModel):
    """Time-series value for a financial metric."""

    fiscal_year: Optional[int] = Field(
        None,
        description="Fiscal year associated with the value.",
        serialization_alias="fiscalYear",
    )
    fiscal_period: Optional[str] = Field(
        None,
        description="Fiscal period label (FY/Q1/Q2/Q3/Q4).",
        serialization_alias="fiscalPeriod",
    )
    period_type: Literal["annual", "quarter", "other"] = Field(
        "other",
        description="Derived period bucket used by the client toggle.",
        serialization_alias="periodType",
    )
    period_end_date: Optional[date] = Field(
        None,
        description="Period end date supplied by DART if available.",
        serialization_alias="periodEndDate",
    )
    value: Optional[float] = Field(None, description="Numeric value converted to float (unitless).")
    unit: Optional[str] = Field(None, description="Measurement unit reported by DART.")
    currency: Optional[str] = Field(None, description="Currency code when provided.")
    reference_no: Optional[str] = Field(
        None,
        description="Underlying filing receipt number to power Evidence Bundle links.",
        serialization_alias="referenceNo",
    )


class FinancialStatementRow(BaseModel):
    """Single metric row displayed inside a financial statement block."""

    metric_code: str = Field(..., description="Normalized metric identifier/code.")
    label: str = Field(..., description="Localized display label for the metric.")
    values: List[FinancialValue] = Field(default_factory=list, description="Chronological metric series.")


class FinancialStatementBlock(BaseModel):
    """Grouped rows for a financial statement (손익/대차/현금흐름)."""

    statement_code: str = Field(..., description="Statement identifier (income_statement/balance_sheet/cash_flow).")
    label: str = Field(..., description="Display label for the statement.")
    rows: List[FinancialStatementRow] = Field(default_factory=list, description="Metric rows contained in the block.")
    description: Optional[str] = Field(
        default=None,
        description="Optional helper copy rendered under the statement header.",
    )


class EvidenceLink(BaseModel):
    """Link metadata connecting a metric to its evidence source."""

    statement_code: str = Field(..., description="Originating statement identifier.")
    statement_label: str = Field(..., description="Statement display label.")
    metric_code: str = Field(..., description="Metric identifier.")
    metric_label: str = Field(..., description="Display label for the metric.")
    period_label: str = Field(..., description="Human-readable period (예: 2024 Q2).")
    reference_no: str = Field(..., description="DART receipt number used to fetch the original evidence.")
    viewer_url: str = Field(..., description="Direct viewer link for the underlying evidence.")
    value: Optional[float] = Field(default=None, description="Metric value reported in the evidence.")
    unit: Optional[str] = Field(default=None, description="Unit associated with the metric value.")


class RestatementHighlight(BaseModel):
    """Summarised view of a correction filing and its numeric impact."""

    receipt_no: str = Field(..., description="Restatement filing receipt number.")
    title: Optional[str] = Field(default=None, description="Restatement title or headline.")
    filed_at: Optional[str] = Field(default=None, description="ISO timestamp when the restatement was filed.")
    report_name: Optional[str] = Field(default=None, description="Originating report name.")
    metric_code: Optional[str] = Field(default=None, description="Metric identifier impacted by the restatement.")
    metric_label: Optional[str] = Field(default=None, description="Display label for the impacted metric.")
    previous_value: Optional[float] = Field(default=None, description="Value before the restatement.")
    current_value: Optional[float] = Field(default=None, description="Value after the restatement.")
    delta_percent: Optional[float] = Field(default=None, description="Percentage change introduced by the restatement.")
    viewer_url: Optional[str] = Field(default=None, description="Direct DART viewer link for the restatement.")
    frequency_percentile: Optional[float] = Field(
        default=None,
        description="Relative frequency percentile within sector/size peer group.",
        serialization_alias="frequencyPercentile",
    )


class FiscalAlignmentInsight(BaseModel):
    """Diagnostic summary explaining how well annual/quarter periods align."""

    latest_annual_period: Optional[str] = Field(default=None, description="Most recent annual period label.")
    latest_quarter_period: Optional[str] = Field(default=None, description="Most recent quarter period label.")
    yoy_delta_percent: Optional[float] = Field(default=None, description="Seasonal YoY delta for the benchmark metric.")
    ttm_quarter_coverage: int = Field(default=0, description="Number of consecutive quarters available for TTM.")
    alignment_status: Literal["good", "warning", "missing"] = Field(
        default="warning", description="Overall alignment heuristic."
    )
    notes: Optional[str] = Field(default=None, description="Helper note rendered on the UI.")


class KeyMetric(BaseModel):
    """Key financial metric extracted from DART summaries."""

    metric_code: str = Field(..., description="Metric identifier (account id)")
    label: str = Field(..., description="Metric label")
    value: Optional[float] = Field(None, description="Numeric value (unitless)")
    unit: Optional[str] = Field(None, description="Reporting unit")
    fiscal_year: Optional[int] = Field(None, description="Fiscal year")
    fiscal_period: Optional[str] = Field(None, description="Fiscal period label (FY/Q1/Q2/Q3)")


class EventItem(BaseModel):
    """Major event extracted from DART DE005."""

    id: uuid.UUID
    event_type: str
    event_name: Optional[str] = None
    event_date: Optional[date] = None
    resolution_date: Optional[date] = None
    report_name: Optional[str] = None
    derived_metrics: dict = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class TopicWeight(BaseModel):
    topic: str
    count: int
    weight: float


class NewsWindowInsight(BaseModel):
    """Aggregated news metrics for dashboard cards."""

    scope: str
    ticker: Optional[str] = None
    window_days: int
    computed_for: datetime

    article_count: int
    avg_sentiment: Optional[float] = None
    sentiment_z: Optional[float] = None
    novelty_kl: Optional[float] = None
    topic_shift: Optional[float] = None
    domestic_ratio: Optional[float] = None
    domain_diversity: Optional[float] = None
    top_topics: List[TopicWeight] = Field(default_factory=list)
    source_reliability: Optional[float] = Field(
        None, description="Heuristic reliability score for the aggregated window"
    )

    model_config = ConfigDict(from_attributes=True)


class CompanySnapshotResponse(BaseModel):
    """Complete snapshot payload for company overview."""

    corp_code: Optional[str] = None
    ticker: Optional[str] = None
    corp_name: Optional[str] = None

    latest_filing: Optional[FilingHeadline] = None
    summary: Optional[SummaryBlock] = None
    financial_statements: List[FinancialStatementBlock] = Field(
        default_factory=list,
        description="Structured financial statement rows grouped by statement type.",
    )
    key_metrics: List[KeyMetric] = Field(default_factory=list)
    major_events: List[EventItem] = Field(default_factory=list)
    news_signals: List[NewsWindowInsight] = Field(default_factory=list)
    recent_filings: List[CompanyFilingSummary] = Field(
        default_factory=list,
        serialization_alias="recentFilings",
        description="Recent filings within the look-back window for the company.",
    )
    restatement_highlights: List[RestatementHighlight] = Field(
        default_factory=list,
        description="Recent correction filings with detected numeric impact.",
    )
    evidence_links: List[EvidenceLink] = Field(
        default_factory=list,
        description="Shortcut mapping from dashboard metrics to DART evidence.",
    )
    fiscal_alignment: Optional[FiscalAlignmentInsight] = Field(
        default=None,
        description="Insight describing annual/quarter alignment readiness.",
    )


class CompanySearchResult(BaseModel):
    """Lightweight metadata for search/autocomplete."""

    corp_code: Optional[str] = Field(None, description="DART corporation code")
    ticker: Optional[str] = Field(None, description="Equity ticker symbol")
    corp_name: Optional[str] = Field(None, description="Legal corporation name")
    latest_report_name: Optional[str] = Field(None, description="Most recent report name")
    latest_filed_at: Optional[datetime] = Field(None, description="Most recent filing timestamp")
    highlight: Optional[str] = Field(None, description="Contextual reason for suggestion")

    model_config = ConfigDict(from_attributes=True)


class CompanySuggestions(BaseModel):
    """Aggregated suggestions for landing page."""

    recent_filings: List[CompanySearchResult] = Field(default_factory=list)
    trending_news: List[CompanySearchResult] = Field(default_factory=list)


class TimelinePoint(BaseModel):
    date: date
    sentiment_z: Optional[float] = None
    price_close: Optional[float] = None
    volume: Optional[float] = None
    event_type: Optional[str] = None


class TimelineResponse(BaseModel):
    window_days: int
    total_points: int
    downsampled_points: int
    points: List[TimelinePoint] = Field(default_factory=list)
