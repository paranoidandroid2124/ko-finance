"""SQLAlchemy models for tenant-scoped SSO providers and SCIM tokens."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from database import Base
from models._metadata_proxy import JSONMetadataProxy


class SsoProvider(Base):
    """Configured SAML/OIDC provider bound to an organisation."""

    __tablename__ = "sso_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True)
    slug = Column(String(160), unique=True, nullable=False)
    provider_type = Column(String(16), nullable=False)
    display_name = Column(String(255), nullable=False)
    issuer = Column(Text, nullable=True)
    audience = Column(Text, nullable=True)
    sp_entity_id = Column(Text, nullable=True)
    acs_url = Column(Text, nullable=True)
    metadata_url = Column(Text, nullable=True)
    idp_sso_url = Column(Text, nullable=True)
    authorization_url = Column(Text, nullable=True)
    token_url = Column(Text, nullable=True)
    userinfo_url = Column(Text, nullable=True)
    redirect_uri = Column(Text, nullable=True)
    scopes = Column(ARRAY(String), nullable=True)
    attribute_mapping = Column(JSONB, nullable=False, default=dict)
    default_plan_tier = Column(String(32), nullable=True)
    default_role = Column(String(32), nullable=False, default="viewer")
    default_org_slug = Column(String(160), nullable=True)
    auto_provision_orgs = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    metadata = JSONMetadataProxy("metadata_json")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<SsoProvider slug={self.slug!r} type={self.provider_type!r}>"


class SsoProviderCredential(Base):
    """Encrypted credential material for a provider (client secrets, certs, etc.)."""

    __tablename__ = "sso_provider_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sso_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    credential_type = Column(String(64), nullable=False)
    secret_encrypted = Column(Text, nullable=False)
    secret_masked = Column(String(128), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(160), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    rotated_at = Column(DateTime(timezone=True), nullable=True)


class ScimToken(Base):
    """Bearer tokens used for SCIM provisioning per provider."""

    __tablename__ = "scim_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sso_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash = Column(Text, nullable=False, unique=True)
    token_prefix = Column(String(16), nullable=False)
    description = Column(String(255), nullable=True)
    created_by = Column(String(160), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    metadata = JSONMetadataProxy("metadata_json")

