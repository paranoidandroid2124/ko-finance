"""Database models for user-defined alert rules and delivery audits."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from database import Base

ALERT_STATUS = Enum(
    "active",
    "paused",
    "archived",
    name="alert_status",
)

DELIVERY_STATUS = Enum(
    "queued",
    "delivered",
    "failed",
    "throttled",
    "skipped",
    name="alert_delivery_status",
)


class AlertRule(Base):
    """Alert configuration persisted per user/org."""

    __tablename__ = "alert_rules"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    org_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    plan_tier = Column(String(32), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(ALERT_STATUS, nullable=False, default="active", index=True)
    condition = Column(JSONB, nullable=False, default=dict)
    channels = Column(JSONB, nullable=False, default=list)
    message_template = Column(Text, nullable=True)
    evaluation_interval_minutes = Column(Integer, nullable=False, default=5)
    window_minutes = Column(Integer, nullable=False, default=60)
    cooldown_minutes = Column(Integer, nullable=False, default=60)
    max_triggers_per_day = Column(Integer, nullable=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_evaluated_at = Column(DateTime(timezone=True), nullable=True)
    throttle_until = Column(DateTime(timezone=True), nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    extras = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def should_evaluate(self, now: datetime) -> bool:
        """Determine whether the rule is due for evaluation."""
        if self.status != "active":
            return False
        if self.throttle_until and self.throttle_until > now:
            return False
        if self.last_evaluated_at is None:
            return True
        interval = max(self.evaluation_interval_minutes or 1, 1)
        due_at = self.last_evaluated_at + timedelta(minutes=interval)
        return due_at <= now

    def remaining_cooldown(self, now: datetime) -> int:
        if self.throttle_until and self.throttle_until > now:
            delta = self.throttle_until - now
            return max(int(delta.total_seconds() // 60), 0)
        if self.last_triggered_at is None:
            return 0
        cooldown = max(self.cooldown_minutes or 0, 0)
        if cooldown == 0:
            return 0
        unlock_at = self.last_triggered_at + timedelta(minutes=cooldown)
        if unlock_at <= now:
            return 0
        return max(int((unlock_at - now).total_seconds() // 60), 0)


class AlertDelivery(Base):
    """Audit record for alert delivery attempts."""

    __tablename__ = "alert_deliveries"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(32), nullable=False)
    status = Column(DELIVERY_STATUS, nullable=False, default="queued", index=True)
    message = Column(Text, nullable=False)
    context = Column(JSONB, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
