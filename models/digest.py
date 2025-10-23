import uuid

from sqlalchemy import Column, Date, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from database import Base


class DailyDigestLog(Base):
    __tablename__ = "daily_digest_logs"
    __table_args__ = (UniqueConstraint("digest_date", "channel", name="uq_daily_digest_logs"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    digest_date = Column(Date, nullable=False)
    channel = Column(String(32), nullable=False, default="telegram")
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["DailyDigestLog"]

