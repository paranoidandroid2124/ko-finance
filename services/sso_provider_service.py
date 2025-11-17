"""Helpers for storing and loading tenant-specific SSO provider configuration."""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Sequence, Tuple

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from core.logging import get_logger
from models.sso_provider import ScimToken, SsoProvider, SsoProviderCredential
from services.auth.common import OidcProviderConfig, SamlProviderConfig
from services.memory import crypto as memory_crypto

logger = get_logger(__name__)

CredentialPayload = Mapping[str, Optional[str]]


@dataclass(frozen=True)
class SsoProviderConfig:
    """Dehydrated provider configuration ready for runtime use."""

    id: uuid.UUID
    slug: str
    provider_type: str
    org_id: Optional[uuid.UUID]
    issuer: Optional[str]
    audience: Optional[str]
    sp_entity_id: Optional[str]
    acs_url: Optional[str]
    metadata_url: Optional[str]
    idp_sso_url: Optional[str]
    authorization_url: Optional[str]
    token_url: Optional[str]
    userinfo_url: Optional[str]
    redirect_uri: Optional[str]
    scopes: Tuple[str, ...]
    attribute_mapping: Mapping[str, Any]
    default_plan_tier: Optional[str]
    default_role: Optional[str]
    default_org_slug: Optional[str]
    auto_provision_orgs: bool
    enabled: bool
    metadata: Mapping[str, Any]
    credentials: CredentialPayload


@dataclass(frozen=True)
class ScimTokenRecord:
    id: uuid.UUID
    provider_id: uuid.UUID
    token_prefix: str
    description: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    last_used_at: Optional[datetime]


def _normalize_slug(slug: str) -> str:
    candidate = (slug or "").strip().lower()
    if not candidate:
        raise ValueError("slug is required")
    return candidate


def _normalize_attribute_mapping(raw: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    mapping: Dict[str, Any] = {}
    if not raw:
        return mapping
    for key, value in raw.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        mapping[normalized_key] = value
    return mapping


def _mask_secret(value: str) -> str:
    stripped = value.strip()
    if len(stripped) <= 8:
        return "*" * len(stripped)
    return f"{stripped[:4]}…{stripped[-4:]}"


def _encrypt_secret(value: str) -> str:
    payload = value.encode("utf-8")
    encrypted = memory_crypto.encrypt(payload)
    return base64.b64encode(encrypted).decode("ascii")


def _decrypt_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    decoded = base64.b64decode(value.encode("ascii"))
    decrypted = memory_crypto.decrypt(decoded)
    return decrypted.decode("utf-8")


def create_sso_provider(
    session: Session,
    *,
    slug: str,
    provider_type: str,
    display_name: str,
    org_id: Optional[uuid.UUID] = None,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    sp_entity_id: Optional[str] = None,
    acs_url: Optional[str] = None,
    metadata_url: Optional[str] = None,
    idp_sso_url: Optional[str] = None,
    authorization_url: Optional[str] = None,
    token_url: Optional[str] = None,
    userinfo_url: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    scopes: Optional[Sequence[str]] = None,
    attribute_mapping: Optional[Mapping[str, Any]] = None,
    default_plan_tier: Optional[str] = None,
    default_role: Optional[str] = "viewer",
    default_org_slug: Optional[str] = None,
    auto_provision_orgs: bool = False,
    metadata: Optional[Mapping[str, Any]] = None,
) -> SsoProvider:
    """Persist a new provider record."""

    normalized_slug = _normalize_slug(slug)
    record = SsoProvider(
        slug=normalized_slug,
        provider_type=provider_type,
        display_name=display_name.strip(),
        org_id=org_id,
        issuer=issuer,
        audience=audience,
        sp_entity_id=sp_entity_id,
        acs_url=acs_url,
        metadata_url=metadata_url,
        idp_sso_url=idp_sso_url,
        authorization_url=authorization_url,
        token_url=token_url,
        userinfo_url=userinfo_url,
        redirect_uri=redirect_uri,
        scopes=list(scopes) if scopes else None,
        attribute_mapping=_normalize_attribute_mapping(attribute_mapping),
        default_plan_tier=default_plan_tier,
        default_role=default_role,
        default_org_slug=default_org_slug,
        auto_provision_orgs=auto_provision_orgs,
        metadata_json=dict(metadata or {}),
    )
    session.add(record)
    session.flush()
    logger.info("Created SSO provider slug=%s type=%s", normalized_slug, provider_type)
    return record


def update_sso_provider(
    session: Session,
    provider_id: uuid.UUID,
    *,
    display_name: Optional[str] = None,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    sp_entity_id: Optional[str] = None,
    acs_url: Optional[str] = None,
    metadata_url: Optional[str] = None,
    idp_sso_url: Optional[str] = None,
    authorization_url: Optional[str] = None,
    token_url: Optional[str] = None,
    userinfo_url: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    scopes: Optional[Sequence[str]] = None,
    attribute_mapping: Optional[Mapping[str, Any]] = None,
    default_plan_tier: Optional[str] = None,
    default_role: Optional[str] = None,
    default_org_slug: Optional[str] = None,
    auto_provision_orgs: Optional[bool] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    enabled: Optional[bool] = None,
) -> SsoProvider:
    """Update mutable provider fields."""

    provider: Optional[SsoProvider] = session.get(SsoProvider, provider_id)
    if not provider:
        raise ValueError(f"Provider {provider_id} not found")

    if display_name is not None:
        provider.display_name = display_name.strip()
    if issuer is not None:
        provider.issuer = issuer
    if audience is not None:
        provider.audience = audience
    if sp_entity_id is not None:
        provider.sp_entity_id = sp_entity_id
    if acs_url is not None:
        provider.acs_url = acs_url
    if metadata_url is not None:
        provider.metadata_url = metadata_url
    if idp_sso_url is not None:
        provider.idp_sso_url = idp_sso_url
    if authorization_url is not None:
        provider.authorization_url = authorization_url
    if token_url is not None:
        provider.token_url = token_url
    if userinfo_url is not None:
        provider.userinfo_url = userinfo_url
    if redirect_uri is not None:
        provider.redirect_uri = redirect_uri
    if scopes is not None:
        provider.scopes = list(scopes)
    if attribute_mapping is not None:
        provider.attribute_mapping = _normalize_attribute_mapping(attribute_mapping)
    if default_plan_tier is not None:
        provider.default_plan_tier = default_plan_tier
    if default_role is not None:
        provider.default_role = default_role
    if default_org_slug is not None:
        provider.default_org_slug = default_org_slug
    if auto_provision_orgs is not None:
        provider.auto_provision_orgs = bool(auto_provision_orgs)
    if metadata is not None:
        provider.metadata_json = dict(metadata)
    if enabled is not None:
        provider.enabled = bool(enabled)
    session.flush()
    return provider


def list_sso_providers(
    session: Session,
    *,
    provider_type: Optional[str] = None,
) -> Sequence[SsoProvider]:
    """Return all providers, optionally filtered by type."""

    statement: Select[Tuple[SsoProvider]] = select(SsoProvider)
    if provider_type:
        statement = statement.where(SsoProvider.provider_type == provider_type)
    statement = statement.order_by(SsoProvider.slug.asc())
    return list(session.execute(statement).scalars())


def get_sso_provider(session: Session, provider_id: uuid.UUID) -> Optional[SsoProvider]:
    return session.get(SsoProvider, provider_id)


def get_provider_by_slug(
    session: Session,
    slug: str,
    *,
    provider_type: Optional[str] = None,
) -> Optional[SsoProvider]:
    normalized_slug = _normalize_slug(slug)
    statement: Select[Tuple[SsoProvider]] = select(SsoProvider).where(SsoProvider.slug == normalized_slug)
    if provider_type:
        statement = statement.where(SsoProvider.provider_type == provider_type)
    return session.execute(statement).scalars().first()


def _load_credentials(session: Session, provider_id: uuid.UUID) -> Dict[str, Optional[str]]:
    statement = select(SsoProviderCredential).where(SsoProviderCredential.provider_id == provider_id)
    creds: MutableMapping[str, Optional[str]] = {}
    for row in session.execute(statement).scalars():
        creds[row.credential_type] = _decrypt_secret(row.secret_encrypted)
    return dict(creds)


def get_masked_credentials(session: Session, provider_id: uuid.UUID) -> Dict[str, Optional[str]]:
    """Return masked credential metadata for admin surfaces."""

    statement = select(SsoProviderCredential).where(SsoProviderCredential.provider_id == provider_id).order_by(
        SsoProviderCredential.credential_type.asc()
    )
    results: Dict[str, Optional[str]] = {}
    for row in session.execute(statement).scalars():
        results[row.credential_type] = row.secret_masked
    return results


def get_provider_config(
    session: Session,
    slug: str,
    *,
    provider_type: Optional[str] = None,
) -> Optional[SsoProviderConfig]:
    provider = get_provider_by_slug(session, slug, provider_type=provider_type)
    if not provider or not provider.enabled:
        return None
    credentials = _load_credentials(session, provider.id)
    scopes: Tuple[str, ...] = tuple(provider.scopes or [])
    return SsoProviderConfig(
        id=provider.id,
        slug=provider.slug,
        provider_type=provider.provider_type,
        org_id=provider.org_id,
        issuer=provider.issuer,
        audience=provider.audience,
        sp_entity_id=provider.sp_entity_id,
        acs_url=provider.acs_url,
        metadata_url=provider.metadata_url,
        idp_sso_url=provider.idp_sso_url,
        authorization_url=provider.authorization_url,
        token_url=provider.token_url,
        userinfo_url=provider.userinfo_url,
        redirect_uri=provider.redirect_uri,
        scopes=scopes,
        attribute_mapping=dict(provider.attribute_mapping or {}),
        default_plan_tier=provider.default_plan_tier,
        default_role=provider.default_role,
        default_org_slug=provider.default_org_slug,
        auto_provision_orgs=provider.auto_provision_orgs,
        enabled=provider.enabled,
        metadata=dict(provider.metadata or {}),
        credentials=credentials,
    )


def store_provider_credential(
    session: Session,
    provider_id: uuid.UUID,
    credential_type: str,
    secret_value: str,
    *,
    created_by: Optional[str] = None,
) -> SsoProviderCredential:
    """Upsert an encrypted credential for the provider."""

    encrypted = _encrypt_secret(secret_value)
    masked = _mask_secret(secret_value)
    existing = (
        session.execute(
            select(SsoProviderCredential).where(
                SsoProviderCredential.provider_id == provider_id,
                SsoProviderCredential.credential_type == credential_type,
            )
        )
        .scalars()
        .first()
    )
    if existing:
        existing.secret_encrypted = encrypted
        existing.secret_masked = masked
        existing.version += 1
        existing.created_by = created_by
        existing.rotated_at = datetime.now()
        result = existing
    else:
        result = SsoProviderCredential(
            provider_id=provider_id,
            credential_type=credential_type,
            secret_encrypted=encrypted,
            secret_masked=masked,
            created_by=created_by,
        )
        session.add(result)
    session.flush()
    return result


def generate_scim_token(
    session: Session,
    provider_id: uuid.UUID,
    *,
    created_by: Optional[str] = None,
    description: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> str:
    """Create and persist a new SCIM bearer token, returning the plaintext token once."""

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token_prefix = raw_token[:10]

    record = ScimToken(
        provider_id=provider_id,
        token_hash=token_hash,
        token_prefix=token_prefix,
        description=description,
        created_by=created_by,
        expires_at=expires_at,
    )
    session.add(record)
    session.flush()
    return raw_token


def list_scim_tokens(session: Session, provider_id: uuid.UUID) -> Sequence[ScimTokenRecord]:
    statement = select(ScimToken).where(ScimToken.provider_id == provider_id).order_by(ScimToken.created_at.desc())
    records = []
    for row in session.execute(statement).scalars():
        records.append(
            ScimTokenRecord(
                id=row.id,
                provider_id=row.provider_id,
                token_prefix=row.token_prefix,
                description=row.description,
                created_by=row.created_by,
                created_at=row.created_at,
                expires_at=row.expires_at,
                revoked_at=row.revoked_at,
                last_used_at=row.last_used_at,
            )
        )
    return records


def resolve_scim_token(session: Session, token: str) -> Tuple[SsoProvider, ScimToken]:
    """Resolve the provider for the given SCIM bearer token."""

    cleaned = (token or "").strip()
    if not cleaned:
        raise ValueError("invalid_token")
    token_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    record = (
        session.execute(select(ScimToken).where(ScimToken.token_hash == token_hash))
        .scalars()
        .first()
    )
    if not record:
        raise ValueError("invalid_token")
    now = datetime.now(timezone.utc)
    if record.revoked_at:
        raise ValueError("token_revoked")
    if record.expires_at and now >= record.expires_at:
        raise ValueError("token_expired")
    provider = session.get(SsoProvider, record.provider_id)
    if not provider or not provider.enabled:
        raise ValueError("provider_unavailable")
    record.last_used_at = now
    session.flush()
    return provider, record


def _attribute_value(mapping: Mapping[str, Any], key: str, default: str) -> str:
    raw = mapping.get(key)
    if raw is None:
        return default
    text = str(raw).strip()
    return text or default


def _normalize_role_mapping(raw: Any) -> Dict[str, str]:
    if isinstance(raw, Mapping):
        normalized: Dict[str, str] = {}
        for key, value in raw.items():
            key_text = str(key).strip().lower()
            value_text = str(value).strip().lower() if isinstance(value, str) else ""
            if key_text and value_text:
                normalized[key_text] = value_text
        if normalized:
            return normalized
    return {}


_DEFAULT_ROLE_MAPPING = {"admin": "admin", "owner": "admin", "editor": "editor", "viewer": "viewer"}


def build_saml_provider_config(runtime: SsoProviderConfig) -> SamlProviderConfig:
    """Convert a persisted provider into an auth-layer config."""

    attr = dict(runtime.attribute_mapping or {})
    metadata = dict(runtime.metadata or {})
    credentials = runtime.credentials
    role_mapping = _normalize_role_mapping(metadata.get("roleMapping") or attr.get("roleMapping")) or dict(
        _DEFAULT_ROLE_MAPPING
    )
    email_attr = _attribute_value(attr, "email", "email")
    name_attr = _attribute_value(attr, "name", "displayName")
    org_attr = _attribute_value(attr, "org", "orgSlug")
    role_attr = _attribute_value(attr, "role", "role")
    plan_tier = runtime.default_plan_tier or "enterprise"
    return SamlProviderConfig(
        enabled=runtime.enabled,
        sp_entity_id=runtime.sp_entity_id or runtime.audience,
        acs_url=runtime.acs_url,
        metadata_url=runtime.metadata_url,
        sp_certificate=credentials.get("saml_sp_certificate"),
        idp_entity_id=runtime.issuer,
        idp_sso_url=runtime.idp_sso_url,
        idp_certificate=credentials.get("saml_idp_certificate"),
        email_attribute=email_attr,
        name_attribute=name_attr,
        org_attribute=org_attr,
        role_attribute=role_attr,
        default_org_slug=runtime.default_org_slug,
        default_role=runtime.default_role or "viewer",
        role_mapping=role_mapping,
        auto_provision_orgs=runtime.auto_provision_orgs,
        default_plan_tier=plan_tier,
    )


def build_oidc_provider_config(runtime: SsoProviderConfig) -> OidcProviderConfig:
    attr = dict(runtime.attribute_mapping or {})
    credentials = runtime.credentials
    scopes = tuple(runtime.scopes or ("openid", "email", "profile"))
    client_id = credentials.get("oidc_client_id") or runtime.audience
    client_secret = credentials.get("oidc_client_secret")
    if not client_id or not client_secret:
        raise ValueError("OIDC provider is missing client credentials.")
    return OidcProviderConfig(
        enabled=runtime.enabled,
        client_id=client_id,
        client_secret=client_secret,
        authorization_url=runtime.authorization_url,
        token_url=runtime.token_url,
        userinfo_url=runtime.userinfo_url,
        redirect_uri=runtime.redirect_uri,
        scopes=scopes,
        default_org_slug=runtime.default_org_slug,
        org_claim=_attribute_value(attr, "org", "org"),
        role_claim=_attribute_value(attr, "role", "role"),
        plan_claim=_attribute_value(attr, "plan", "plan"),
        email_claim=_attribute_value(attr, "email", "email"),
        name_claim=_attribute_value(attr, "name", "name"),
        default_role=runtime.default_role or "viewer",
        role_mapping=_normalize_role_mapping(attr.get("roleMapping")) or dict(_DEFAULT_ROLE_MAPPING),
        auto_provision_orgs=runtime.auto_provision_orgs,
        default_plan_tier=runtime.default_plan_tier or "enterprise",
    )
