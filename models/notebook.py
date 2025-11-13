"""SQLAlchemy models for Research Notebook entities."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.sql import func

from database import Base
from models._metadata_proxy import JSONMetadataProxy


class Notebook(Base):
    """Notebook container holding collaborative highlights."""

    __tablename__ = "notebooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    tags = Column(ARRAY(String), nullable=False, default=list)
    cover_color = Column(String(32), nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    metadata = JSONMetadataProxy("metadata_json")
    entry_count = Column(Integer, nullable=False, default=0)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotebookEntry(Base):
    """Individual highlight or annotation block."""

    __tablename__ = "notebook_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notebook_id = Column(UUID(as_uuid=True), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    highlight = Column(Text, nullable=False)
    annotation = Column(Text, nullable=True)
    annotation_format = Column(String(32), nullable=False, default="markdown")
    tags = Column(ARRAY(String), nullable=False, default=list)
    source = Column(JSONB, nullable=False, default=dict)
    is_pinned = Column(Boolean, nullable=False, default=False)
    position = Column(Integer, nullable=False, default=0, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotebookShare(Base):
    """Shareable link with optional password and expiry."""

    __tablename__ = "notebook_shares"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notebook_id = Column(UUID(as_uuid=True), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(Text, nullable=False, unique=True, index=True)
    created_by = Column(UUID(as_uuid=True), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    password_hash = Column(Text, nullable=True)
    password_hint = Column(Text, nullable=True)
    access_scope = Column(String(32), nullable=False, default="view")
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["Notebook", "NotebookEntry", "NotebookShare"]
