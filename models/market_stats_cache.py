import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class MarketStatsCache(Base):
    """Precomputed percentile thresholds for market/grouped metrics."""

    __tablename__ = "market_stats_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    segment = Column(String, nullable=False, comment="Grouping dimension (e.g., cap_bucket, sector)")
    segment_value = Column(String, nullable=False, comment="Grouping value (e.g., 대형주/IT)")
    metric = Column(String, nullable=False, comment="Metric name (e.g., restatement_freq)")
    percentile = Column(Float, nullable=False, comment="Percentile label (0-100)")
    value = Column(Float, nullable=True, comment="Threshold value at the percentile")
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
