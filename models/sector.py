"""SQLAlchemy models supporting sector-level market mood metrics."""

from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class Sector(Base):
    """Reference data for tracked market sectors."""

    __tablename__ = "sectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<Sector(id={self.id}, slug='{self.slug}', name='{self.name}')>"


class NewsArticleSector(Base):
    """Link table mapping processed news articles to sectors."""

    __tablename__ = "news_article_sectors"

    article_id = Column(UUID(as_uuid=True), ForeignKey("news_signals.id", ondelete="CASCADE"), primary_key=True)
    sector_id = Column(Integer, ForeignKey("sectors.id", ondelete="CASCADE"), primary_key=True)
    weight = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SectorDailyMetric(Base):
    """Daily sentiment and volume aggregates per sector."""

    __tablename__ = "sector_daily_metrics"

    sector_id = Column(Integer, ForeignKey("sectors.id", ondelete="CASCADE"), primary_key=True)
    date = Column(Date, primary_key=True)
    sent_mean = Column(Float)
    sent_std = Column(Float)
    volume = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SectorWindowMetric(Base):
    """Rolling window metrics (7/30/90-day) used for hotspot and sparkline views."""

    __tablename__ = "sector_window_metrics"

    sector_id = Column(Integer, ForeignKey("sectors.id", ondelete="CASCADE"), primary_key=True)
    window_days = Column(Integer, primary_key=True)
    asof_date = Column(Date, primary_key=True)
    sent_mean = Column(Float)
    vol_sum = Column(Integer)
    sent_z = Column(Float)
    vol_z = Column(Float)
    delta_sent_7d = Column(Float)
    top_article_id = Column(UUID(as_uuid=True), ForeignKey("news_signals.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
