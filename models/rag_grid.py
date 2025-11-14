"""SQLAlchemy models for asynchronous RAG grid jobs."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class RagGridJob(Base):
    __tablename__ = "rag_grid_jobs"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String(32), nullable=False, index=True)
    trace_id = Column(String(64), nullable=True)
    requested_by = Column(UUID(as_uuid=True), nullable=True)
    ticker_count = Column(Integer, nullable=False)
    question_count = Column(Integer, nullable=False)
    total_cells = Column(Integer, nullable=False)
    completed_cells = Column(Integer, nullable=False, default=0)
    failed_cells = Column(Integer, nullable=False, default=0)
    payload = Column(JSONB, nullable=False, default=dict)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    cells = relationship("RagGridCell", back_populates="job", cascade="all, delete-orphan")


class RagGridCell(Base):
    __tablename__ = "rag_grid_cells"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("rag_grid_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(64), nullable=False, index=True)
    question = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, index=True)
    latency_ms = Column(Integer, nullable=True)
    answer = Column(Text, nullable=True)
    evidence = Column(JSONB, nullable=True)
    warnings = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    job = relationship("RagGridJob", back_populates="cells")


__all__ = ["RagGridJob", "RagGridCell"]
