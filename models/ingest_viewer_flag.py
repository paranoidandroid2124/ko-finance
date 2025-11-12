import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from database import Base


class IngestViewerFlag(Base):
    __tablename__ = "ingest_viewer_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corp_code = Column(String, unique=True, nullable=False)
    fallback_enabled = Column(Boolean, nullable=False, default=True)
    reason = Column(Text, nullable=True)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

