from __future__ import annotations

import uuid

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class TossWebhookEventLog(Base):
    """토스 웹훅 감사 로그를 저장하는 테이블."""

    __tablename__ = "payments_toss_webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transmission_id = Column(String, nullable=True, index=True)
    order_id = Column(String, nullable=True, index=True)
    event_type = Column(String, nullable=True, index=True)
    status = Column(String, nullable=True)
    result = Column(String, nullable=False, index=True)
    dedupe_key = Column(String, nullable=True, index=True)
    retry_count = Column(Integer, nullable=True)
    message = Column(Text, nullable=True)
    context = Column(JSON, nullable=True)
    payload = Column(JSON, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
