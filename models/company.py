import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class CorpMetric(Base):
    """Normalized financial metrics sourced from DART disclosures."""

    __tablename__ = "corp_metrics"
    __table_args__ = (
        UniqueConstraint(
            "corp_code",
            "metric_code",
            "fiscal_year",
            "fiscal_period",
            "source",
            name="uq_corp_metrics_metric_scope",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corp_code = Column(String, index=True, nullable=False)
    corp_name = Column(String, nullable=True)
    ticker = Column(String, index=True, nullable=True)

    metric_code = Column(String, nullable=False, index=True, comment="Metric identifier (account id)")
    metric_name = Column(String, nullable=False, comment="Human readable metric name")
    metric_group = Column(String, nullable=True, comment="Optional group/category name")

    fiscal_year = Column(Integer, nullable=False, comment="Fiscal year associated with the metric")
    fiscal_period = Column(String, nullable=False, comment="Reporting period (eg. FY, Q1, Q2, Q3)")
    period_end_date = Column(Date, nullable=True, comment="Period end date if supplied by DART")

    value = Column(Float, nullable=True, comment="Numeric value converted to float (unitless)")
    unit = Column(String, nullable=True, comment="Measurement unit reported by DART")
    currency = Column(String, nullable=True, comment="Currency code if supplied")

    raw_payload = Column(JSON, nullable=True, comment="Original payload segment from DART response")
    source = Column(String, nullable=False, comment="DART endpoint or derived source identifier")
    reference_no = Column(String, nullable=True, index=True, comment="Related filing receipt number")

    observed_at = Column(DateTime(timezone=True), nullable=True, comment="Observation timestamp when available")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FilingEvent(Base):
    """Structured major event extracted from DART disclosures (DE005)."""

    __tablename__ = "filing_events"
    __table_args__ = (
        UniqueConstraint("receipt_no", "event_type", "event_name", name="uq_filing_events_identity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corp_code = Column(String, index=True, nullable=False)
    corp_name = Column(String, nullable=True)
    ticker = Column(String, index=True, nullable=True)

    receipt_no = Column(String, index=True, nullable=False, comment="Related filing receipt number")
    report_name = Column(String, nullable=True, comment="Originating report name")
    event_type = Column(String, nullable=False, index=True, comment="DART provided major issue type code/name")
    event_name = Column(String, nullable=True, comment="Detailed event headline/title")
    event_date = Column(Date, nullable=True, comment="Effective date of the event if provided")
    resolution_date = Column(Date, nullable=True, comment="Resolution/decision date if provided")

    payload = Column(JSON, nullable=True, comment="Raw payload dictionary returned by DART")
    derived_metrics = Column(JSON, nullable=True, comment="Computed helper metrics for UI summaries")

    source = Column(String, nullable=False, comment="DART endpoint identifier")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InsiderTransaction(Base):
    """Insider / major shareholder transaction parsed from DART DE004."""

    __tablename__ = "insider_transactions"
    __table_args__ = (
        UniqueConstraint("receipt_no", "person_name", "transaction_date", name="uq_insider_transaction_scope"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corp_code = Column(String, index=True, nullable=False)
    corp_name = Column(String, nullable=True)
    ticker = Column(String, index=True, nullable=True)

    receipt_no = Column(String, index=True, nullable=False)
    report_name = Column(String, nullable=True)

    person_name = Column(String, nullable=False, comment="Insider / major shareholder name")
    relation = Column(String, nullable=True, comment="Relation/position of the person")
    transaction_type = Column(String, nullable=True, comment="Buy/Sell/Other classification")

    transaction_date = Column(Date, nullable=True, comment="Effective date of the share change")
    shares_before = Column(Float, nullable=True, comment="Shares held before the transaction")
    shares_after = Column(Float, nullable=True, comment="Shares held after the transaction")
    shares_change = Column(Float, nullable=True, comment="Net share change (after-before)")

    ratio_before = Column(Float, nullable=True, comment="Ownership ratio before transaction")
    ratio_after = Column(Float, nullable=True, comment="Ownership ratio after transaction")
    ratio_change = Column(Float, nullable=True, comment="Ownership ratio delta")

    acquisition_amount = Column(Float, nullable=True, comment="Acquisition/disposal amount if supplied")
    payload = Column(JSON, nullable=True, comment="Raw payload dictionary from DART response")
    source = Column(String, nullable=False, comment="DART endpoint identifier")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


__all__ = ["CorpMetric", "FilingEvent", "InsiderTransaction"]
