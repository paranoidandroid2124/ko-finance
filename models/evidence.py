"""Evidence snapshot model for RAG diff tracking."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from database import Base


class EvidenceSnapshot(Base):
    """Stores versioned evidence payloads for diff comparisons."""

    __tablename__ = "evidence_snapshots"

    urn_id = Column(Text, primary_key=True)
    snapshot_hash = Column(Text, primary_key=True)
    previous_snapshot_hash = Column(Text, nullable=True)
    diff_type = Column(String, nullable=False, default="unknown")
    payload = Column(JSONB, nullable=False)
    author = Column(String, nullable=True)
    process = Column(String, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

