"""SQLAlchemy models backing the Market Mood pipeline."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    ARRAY,
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class NewsSignal(Base):
    """Store per-article sentiment signals for Market Mood."""

    __tablename__ = "news_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String, index=True, nullable=True, comment="Optional equity ticker")
    source = Column(String, nullable=False, comment="Feed source or publisher name")
    url = Column(String, nullable=False, unique=True, comment="Canonical article URL")
    headline = Column(String, nullable=False, comment="Article headline")
    summary = Column(Text, nullable=True, comment="Optional extractive summary")
    license_type = Column(String, nullable=True, comment="Normalised license label (e.g. KOGL 유형)")
    license_url = Column(String, nullable=True, comment="License reference URL")
    published_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Published timestamp",
    )

    sentiment = Column(Float, nullable=True, comment="LLM sentiment score (-1.0 ~ 1.0)")
    topics = Column(ARRAY(String), nullable=True, comment="Topical keywords identified by LLM")
    evidence = Column(JSON, nullable=True, comment="Model supplied rationales or anchors")
    source_reliability = Column(Float, nullable=True, comment="Heuristic source reliability score (0~1)")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Row creation time",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Row update time",
    )

    def __repr__(self) -> str:
        return f"<NewsSignal(id={self.id}, headline='{self.headline}')>"


class NewsObservation(Base):
    """Aggregate fifteen-minute Market Mood observations."""

    __tablename__ = "news_observations"
    __table_args__ = (UniqueConstraint("window_start", name="uq_news_observations_window_start"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    window_start = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Observation window start (UTC)",
    )
    window_end = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Observation window end (UTC)",
    )

    article_count = Column(Integer, nullable=False, default=0, comment="Articles observed in window")
    positive_count = Column(Integer, nullable=False, default=0, comment="Positive sentiment articles")
    neutral_count = Column(Integer, nullable=False, default=0, comment="Neutral sentiment articles")
    negative_count = Column(Integer, nullable=False, default=0, comment="Negative sentiment articles")

    avg_sentiment = Column(Float, nullable=True, comment="Average sentiment score")
    min_sentiment = Column(Float, nullable=True, comment="Minimum sentiment score")
    max_sentiment = Column(Float, nullable=True, comment="Maximum sentiment score")

    top_topics = Column(JSON, nullable=True, comment="Top topics with counts for the window")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Row creation time",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Row update time",
    )

    def __repr__(self) -> str:
        return f"<NewsObservation(window_start={self.window_start}, articles={self.article_count})>"


class NewsWindowAggregate(Base):
    """Longer horizon aggregated metrics for dashboard signals."""

    __tablename__ = "news_window_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "scope",
            "ticker",
            "window_days",
            "computed_for",
            name="uq_news_window_scope",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope = Column(String, nullable=False, default="global", comment="Aggregation scope label (global/sector/etc.)")
    ticker = Column(String, index=True, nullable=True, comment="Optional ticker scope")
    window_days = Column(Integer, nullable=False, comment="Number of days covered by the aggregation window")
    computed_for = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Reference timestamp (window end) the metrics correspond to",
    )

    article_count = Column(Integer, nullable=False, default=0, comment="Articles counted in the window")
    avg_sentiment = Column(Float, nullable=True, comment="Mean sentiment score across the window")
    sentiment_z = Column(Float, nullable=True, comment="Z-score of sentiment relative to global baseline")

    novelty_kl = Column(Float, nullable=True, comment="Topic novelty via KL divergence against trailing window")
    topic_shift = Column(Float, nullable=True, comment="Topic drift measured by cosine distance")

    domestic_ratio = Column(Float, nullable=True, comment="Share of domestic sources (0~1)")
    domain_diversity = Column(Float, nullable=True, comment="Unique domain diversity ratio")
    source_reliability = Column(Float, nullable=True, comment="Average source reliability for window")

    top_topics = Column(JSON, nullable=True, comment="Top topics distribution for the window")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return (
            f"<NewsWindowAggregate(scope={self.scope}, ticker={self.ticker}, "
            f"window_days={self.window_days}, computed_for={self.computed_for})>"
        )
