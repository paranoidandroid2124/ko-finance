from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from database import Base


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


__all__ = [
    "EventRecord",
    "Price",
    "EventStudyResult",
    "EventSummary",
    "EventWatchlist",
]
