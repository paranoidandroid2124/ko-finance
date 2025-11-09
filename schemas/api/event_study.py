"""Pydantic schemas describing event study endpoints."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class EventStudyPoint(BaseModel):
    """Series point used for AAR/CAAR charts."""

    t: int = Field(..., description="Event-day index relative to disclosure date.")
    value: float = Field(..., description="Metric value for the given point.")

    model_config = ConfigDict(populate_by_name=True, json_schema_extra={"examples": [{"t": 0, "value": 0.0123}]})


class EventStudyHistogramBin(BaseModel):
    """Histogram bin describing CAAR distribution."""

    bin: int
    range: List[float]
    count: int


class EventStudySummaryItem(BaseModel):
    """Aggregated event study statistics for a specific event type."""

    event_type: str = Field(..., serialization_alias="eventType")
    scope: str
    window: str
    as_of: date = Field(..., serialization_alias="asOf")
    n: int
    hit_rate: float = Field(..., serialization_alias="hitRate")
    mean_caar: float = Field(..., serialization_alias="meanCaar")
    ci_lo: float = Field(..., serialization_alias="ciLo")
    ci_hi: float = Field(..., serialization_alias="ciHi")
    p_value: float = Field(..., serialization_alias="pValue")
    aar: List[EventStudyPoint]
    caar: List[EventStudyPoint]
    dist: List[EventStudyHistogramBin] = Field(default_factory=list)
    cap_bucket: Optional[str] = Field(default=None, serialization_alias="capBucket")
    market: Optional[str] = None


class EventStudySummaryResponse(BaseModel):
    """Response payload for summary endpoint."""

    start: int
    end: int
    scope: str
    significance: float
    results: List[EventStudySummaryItem]


class EventStudyEventItem(BaseModel):
    """Single disclosure event decorated with CAAR metadata."""

    receipt_no: str = Field(..., serialization_alias="receiptNo")
    corp_code: Optional[str] = Field(default=None, serialization_alias="corpCode")
    corp_name: Optional[str] = Field(default=None, serialization_alias="corpName")
    ticker: Optional[str] = None
    event_type: str = Field(..., serialization_alias="eventType")
    market: Optional[str] = None
    event_date: Optional[date] = Field(default=None, serialization_alias="eventDate")
    amount: Optional[float] = None
    ratio: Optional[float] = None
    method: Optional[str] = None
    score: Optional[float] = None
    caar: Optional[float] = Field(default=None, description="CAR at requested window end.")
    aar_peak_day: Optional[int] = Field(default=None, serialization_alias="aarPeakDay")
    viewer_url: Optional[str] = Field(default=None, serialization_alias="viewerUrl")
    cap_bucket: Optional[str] = Field(default=None, serialization_alias="capBucket")
    market_cap: Optional[float] = Field(default=None, serialization_alias="marketCap")


class EventStudyEventsResponse(BaseModel):
    """Paginated response for recent event list."""

    total: int
    limit: int
    offset: int
    window_end: int = Field(..., serialization_alias="windowEnd")
    events: List[EventStudyEventItem]


class EventStudySeriesPoint(BaseModel):
    """Detailed AR/CAR series for a specific event."""

    t: int
    ar: Optional[float] = None
    car: Optional[float] = None


class EventStudyEventDetail(BaseModel):
    """Detailed event payload including AR/CAR series."""

    receipt_no: str = Field(..., serialization_alias="receiptNo")
    corp_code: Optional[str] = Field(default=None, serialization_alias="corpCode")
    corp_name: Optional[str] = Field(default=None, serialization_alias="corpName")
    ticker: Optional[str] = None
    event_type: str = Field(..., serialization_alias="eventType")
    event_date: Optional[date] = Field(default=None, serialization_alias="eventDate")
    market: Optional[str] = None
    scope: str = "market"
    window: str
    viewer_url: Optional[str] = Field(default=None, serialization_alias="viewerUrl")
    series: List[EventStudySeriesPoint] = Field(default_factory=list)
    cap_bucket: Optional[str] = Field(default=None, serialization_alias="capBucket")
    market_cap: Optional[float] = Field(default=None, serialization_alias="marketCap")
