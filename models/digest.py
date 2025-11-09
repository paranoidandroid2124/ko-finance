import uuid

from sqlalchemy import Column, Date, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from database import Base


class DailyDigestLog(Base):
    __tablename__ = "daily_digest_logs"
    __table_args__ = (UniqueConstraint("digest_date", "channel", name="uq_daily_digest_logs"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    digest_date = Column(Date, nullable=False)
    channel = Column(String(32), nullable=False, default="telegram")
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DigestSnapshot(Base):
    __tablename__ = "digest_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "digest_date",
            "timeframe",
            "channel",
            "user_id",
            "org_id",
            name="uq_digest_snapshots_scope",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    digest_date = Column(Date, nullable=False)
    timeframe = Column(String(16), nullable=False, default="daily")
    channel = Column(String(32), nullable=False, default="dashboard")
    user_id = Column(UUID(as_uuid=True), nullable=True)
    org_id = Column(UUID(as_uuid=True), nullable=True)
    payload = Column(JSONB, nullable=False)
    llm_model = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


__all__ = ["DailyDigestLog", "DigestSnapshot"]
