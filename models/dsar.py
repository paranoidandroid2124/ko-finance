"""SQLAlchemy model for DSAR (data subject access request) tracking."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from database import Base
from models._metadata_proxy import JSONMetadataProxy

REQUEST_TYPE = Enum("export", "delete", name="dsar_request_type", create_type=False)
REQUEST_STATUS = Enum("pending", "processing", "completed", "failed", name="dsar_request_status", create_type=False)


class DSARRequest(Base):
    """Track export/delete requests for compliance workflows."""

    __tablename__ = "dsar_requests"
    __table_args__ = (
        UniqueConstraint("id", name="pk_dsar_requests"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    request_type = Column(REQUEST_TYPE, nullable=False)
    status = Column(REQUEST_STATUS, nullable=False, default="pending", index=True)
    channel = Column(String(64), nullable=False, default="self_service")
    requested_by = Column(UUID(as_uuid=True), nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    artifact_path = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)  # type: ignore[assignment]
    metadata = JSONMetadataProxy("metadata_json")  # type: ignore[assignment]


__all__ = ["DSARRequest"]
