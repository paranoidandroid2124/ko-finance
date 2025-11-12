import uuid

from sqlalchemy import JSON, Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from database import Base


class IngestDeadLetter(Base):
    __tablename__ = "ingest_dead_letters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_name = Column(String, nullable=False, index=True)
    receipt_no = Column(String, nullable=True, index=True)
    corp_code = Column(String, nullable=True)
    ticker = Column(String, nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    error = Column(Text, nullable=False)
    retries = Column(Integer, nullable=False, default=0)
    status = Column(
        Enum("pending", "requeued", "completed", name="ingest_dlq_status", create_type=False),
        nullable=False,
        default="pending",
    )
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

