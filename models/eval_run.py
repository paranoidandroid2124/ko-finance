import uuid

from sqlalchemy import Column, DateTime, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from database import Base


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    suite = Column(String, nullable=False)
    pipeline_version = Column(String, nullable=True)
    metrics = Column(JSON, nullable=False)
