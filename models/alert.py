"""Database models for user-defined alert rules and delivery audits."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional

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
    trigger = Column(JSONB, nullable=False, default=dict)
    trigger_type = Column(String(32), nullable=False, default="filing", index=True)
    filters = Column(JSONB, nullable=False, default=dict)
    state = Column(JSONB, nullable=False, default=dict)
    channel_failures = Column(JSONB, nullable=False, default=dict)
    channels = Column(JSONB, nullable=False, default=list)
    message_template = Column(Text, nullable=True)
    frequency = Column(JSONB, nullable=False, default=dict)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_evaluated_at = Column(DateTime(timezone=True), nullable=True)
    cooled_until = Column(DateTime(timezone=True), nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    extras = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ------------------------------------------------------------------
    # Derived helpers for legacy consumers
    # ------------------------------------------------------------------

    @property
    def condition(self) -> Dict[str, object]:
        trigger_payload = self.trigger or {}
        return trigger_payload if isinstance(trigger_payload, dict) else {}

    @condition.setter
    def condition(self, value: Optional[Dict[str, object]]) -> None:
        self.trigger = value or {}

    @property
    def throttle_until(self) -> Optional[datetime]:
        return self.cooled_until

    @throttle_until.setter
    def throttle_until(self, value: Optional[datetime]) -> None:
        self.cooled_until = value

    def _frequency_payload(self) -> Dict[str, object]:
        payload = self.frequency or {}
        return payload if isinstance(payload, dict) else {}

    def _frequency_int(self, key: str, default: int, *, minimum: int = 0) -> int:
        value = self._frequency_payload().get(key)
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            candidate = default
        return max(candidate, minimum)

    def _frequency_optional_int(self, key: str) -> Optional[int]:
        value = self._frequency_payload().get(key)
        if value in (None, "", False):
            return None
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            return None
        return candidate if candidate >= 1 else None

    @property
    def evaluation_interval_minutes(self) -> int:
        return self._frequency_int("evaluationIntervalMinutes", default=5, minimum=1)

    @evaluation_interval_minutes.setter
    def evaluation_interval_minutes(self, value: int) -> None:
        payload = self._frequency_payload()
        payload["evaluationIntervalMinutes"] = max(int(value or 1), 1)
        self.frequency = payload

    @property
    def window_minutes(self) -> int:
        return self._frequency_int("windowMinutes", default=60, minimum=5)

    @window_minutes.setter
    def window_minutes(self, value: int) -> None:
        payload = self._frequency_payload()
        payload["windowMinutes"] = max(int(value or 5), 5)
        self.frequency = payload

    @property
    def cooldown_minutes(self) -> int:
        return self._frequency_int("cooldownMinutes", default=60, minimum=0)

    @cooldown_minutes.setter
    def cooldown_minutes(self, value: int) -> None:
        payload = self._frequency_payload()
        payload["cooldownMinutes"] = max(int(value or 0), 0)
        self.frequency = payload

    @property
    def max_triggers_per_day(self) -> Optional[int]:
        return self._frequency_optional_int("maxTriggersPerDay")

    @max_triggers_per_day.setter
    def max_triggers_per_day(self, value: Optional[int]) -> None:
        payload = self._frequency_payload()
        if value in (None, "", 0):
            payload["maxTriggersPerDay"] = None
        else:
            payload["maxTriggersPerDay"] = max(int(value), 1)
        self.frequency = payload

    def should_evaluate(self, now: datetime) -> bool:
        """Determine whether the rule is due for evaluation."""
        if self.status != "active":
            return False
        if self.cooled_until and self.cooled_until > now:
            return False
        if self.last_evaluated_at is None:
            return True
        interval = max(self.evaluation_interval_minutes or 1, 1)
        due_at = self.last_evaluated_at + timedelta(minutes=interval)
        return due_at <= now

    def remaining_cooldown(self, now: datetime) -> int:
        if self.cooled_until and self.cooled_until > now:
            delta = self.cooled_until - now
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
    event_ref = Column(JSONB, nullable=True)
    trigger_hash = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
