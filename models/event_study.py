import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database import Base
from models._metadata_proxy import JSONMetadataProxy


class EventRecord(Base):
    """Normalized corporate action / disclosure event sourced from DART."""

    __tablename__ = "events"

    rcept_no = Column(String, primary_key=True)
    corp_code = Column(String, nullable=False, index=True)
    ticker = Column(String, nullable=True, index=True)
    corp_name = Column(String, nullable=True)
    event_type = Column(String, nullable=False, index=True)
    event_date = Column(Date, nullable=True)
    amount = Column(Numeric, nullable=True)
    ratio = Column(Numeric, nullable=True)
    shares = Column(BigInteger, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    method = Column(String, nullable=True)
    score = Column(Numeric, nullable=True)
    domain = Column(String, nullable=True, index=True)
    subtype = Column(String, nullable=True)
    confidence = Column(Numeric, nullable=True)
    is_negative = Column(Boolean, nullable=False, default=False, server_default="false")
    is_restatement = Column(Boolean, nullable=False, default=False, server_default="false")
    matches = Column(JSONB, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=True)
    metadata = JSONMetadataProxy("metadata_json")
    market_cap = Column(Numeric, nullable=True)
    cap_bucket = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source_url = Column(Text, nullable=True)


class Price(Base):
    """End-of-day equity price or benchmark series."""

    __tablename__ = "prices"
    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    open = Column(Numeric, nullable=True)
    high = Column(Numeric, nullable=True)
    low = Column(Numeric, nullable=True)
    close = Column(Numeric, nullable=True)
    adj_close = Column(Numeric, nullable=True)
    volume = Column(BigInteger, nullable=True)
    ret = Column(Numeric, nullable=True)
    benchmark = Column(Boolean, nullable=False, default=False, server_default="false")


class EventStudyResult(Base):
    """AR/CAR series for each event and event-day index."""

    __tablename__ = "event_study"
    rcept_no = Column(
        String,
        ForeignKey("events.rcept_no", ondelete="CASCADE"),
        primary_key=True,
    )
    t = Column(SmallInteger, primary_key=True)
    ar = Column(Numeric, nullable=True)
    car = Column(Numeric, nullable=True)


class EventSummary(Base):
    """Aggregated statistics (AAR/CAAR/CI) for event cohorts."""

    __tablename__ = "event_summary"
    asof = Column(Date, primary_key=True)
    event_type = Column(String, primary_key=True)
    window = Column(String, primary_key=True)
    scope = Column(String, primary_key=True, default="market")
    cap_bucket = Column(String, primary_key=True, default="ALL")
    filters = Column(JSONB, nullable=True)
    n = Column(BigInteger, nullable=False)
    aar = Column(JSONB, nullable=True)
    caar = Column(JSONB, nullable=True)
    hit_rate = Column(Numeric, nullable=True)
    mean_caar = Column(Numeric, nullable=True)
    ci_lo = Column(Numeric, nullable=True)
    ci_hi = Column(Numeric, nullable=True)
    p_value = Column(Numeric, nullable=True)
    dist = Column(JSONB, nullable=True)


class EventWatchlist(Base):
    """Configured list of symbols included in the event study pipeline."""

    __tablename__ = "event_watchlist"
    __table_args__ = (
        UniqueConstraint("ticker", "symbol_type", name="uq_event_watchlist_symbol"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    corp_code = Column(String, nullable=True)
    corp_name = Column(String, nullable=True)
    ticker = Column(String, nullable=True, index=True)
    market = Column(String, nullable=True)
    symbol_type = Column(String, nullable=False, default="stock")
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    extra_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EventAlertMatch(Base):
    """Alert rule associations created when an event triggers a watchlist rule."""

    __tablename__ = "event_alert_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String, ForeignKey("events.rcept_no", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    match_score = Column(Numeric, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    metadata = JSONMetadataProxy("metadata_json")
    matched_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EventIngestJob(Base):
    """Book-keeps batch ingestion windows so we can resume or monitor progress."""

    __tablename__ = "event_ingest_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    window_start = Column(Date, nullable=False)
    window_end = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="pending")
    events_created = Column(Integer, nullable=False, default=0)
    events_skipped = Column(Integer, nullable=False, default=0)
    errors = Column(JSONB, nullable=False, default=dict)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    metadata = JSONMetadataProxy("metadata_json")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


__all__ = [
    "EventRecord",
    "Price",
    "EventStudyResult",
    "EventSummary",
    "EventWatchlist",
    "EventAlertMatch",
    "EventIngestJob",
]
