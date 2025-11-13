"""SQLAlchemy models for Light RBAC organisations and memberships."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from database import Base
from models._metadata_proxy import JSONMetadataProxy


class OrgRole(Base):
    """Role catalog (viewer/editor/admin)."""

    __tablename__ = "org_roles"
    __table_args__ = {"extend_existing": True}

    key = Column(String(32), primary_key=True)
    rank = Column(Integer, nullable=False, default=10)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Org(Base):
    """Organisation registry reused by entitlements and RBAC."""

    __tablename__ = "orgs"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(160), unique=True, nullable=True)
    name = Column(String(160), nullable=False)
    status = Column(String(32), nullable=False, default="active")
    default_role = Column(String(32), ForeignKey("org_roles.key", onupdate="CASCADE"), nullable=False, default="viewer")
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    metadata = JSONMetadataProxy("metadata_json")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UserOrg(Base):
    """User membership per organisation with invite metadata."""

    __tablename__ = "user_orgs"
    __table_args__ = {"extend_existing": True}

    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_key = Column(String(32), ForeignKey("org_roles.key", onupdate="CASCADE"), nullable=False, default="viewer")
    status = Column(String(16), nullable=False, default="active")
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    invited_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    metadata = JSONMetadataProxy("metadata_json")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


__all__ = ["Org", "OrgRole", "UserOrg"]
