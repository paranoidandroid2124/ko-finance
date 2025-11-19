"""SQLAlchemy models for value-chain relations."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class ValueChainEdge(Base):
    """Store supplier/customer/competitor relations extracted from unstructured data."""

    __tablename__ = "value_chain_edges"
    __table_args__ = (
        UniqueConstraint(
            "center_ticker",
            "relation_type",
            "related_label",
            name="uq_value_chain_edge",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_ticker = Column(String, nullable=False, index=True)
    relation_type = Column(String, nullable=False, index=True)  # supplier | customer | competitor
    related_ticker = Column(String, nullable=True, index=True)
    related_label = Column(String, nullable=False)
    weight = Column(Float, nullable=True)
    evidence = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


__all__ = ["ValueChainEdge"]
