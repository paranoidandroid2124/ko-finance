-- Multi-tenant SSO provider + SCIM token schema

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS sso_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES orgs(id) ON DELETE CASCADE,
    slug TEXT UNIQUE NOT NULL,
    provider_type TEXT NOT NULL CHECK (provider_type IN ('saml','oidc')),
    display_name TEXT NOT NULL,
    issuer TEXT,
    audience TEXT,
    sp_entity_id TEXT,
    acs_url TEXT,
    metadata_url TEXT,
    idp_sso_url TEXT,
    authorization_url TEXT,
    token_url TEXT,
    userinfo_url TEXT,
    redirect_uri TEXT,
    scopes TEXT[],
    attribute_mapping JSONB NOT NULL DEFAULT '{}'::jsonb,
    default_plan_tier TEXT,
    default_role TEXT DEFAULT 'viewer',
    default_org_slug TEXT,
    auto_provision_orgs BOOLEAN NOT NULL DEFAULT FALSE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sso_providers_org
    ON sso_providers (org_id);

CREATE INDEX IF NOT EXISTS idx_sso_providers_type
    ON sso_providers (provider_type);

CREATE OR REPLACE FUNCTION touch_sso_providers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sso_providers_updated_at ON sso_providers;
CREATE TRIGGER trg_sso_providers_updated_at
BEFORE UPDATE ON sso_providers
FOR EACH ROW
EXECUTE FUNCTION touch_sso_providers_updated_at();

CREATE TABLE IF NOT EXISTS sso_provider_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES sso_providers(id) ON DELETE CASCADE,
    credential_type TEXT NOT NULL CHECK (
        credential_type IN (
            'saml_idp_certificate',
            'saml_sp_certificate',
            'oidc_client_id',
            'oidc_client_secret'
        )
    ),
    secret_encrypted TEXT NOT NULL,
    secret_masked TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rotated_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_sso_credentials_provider_type
    ON sso_provider_credentials(provider_id, credential_type);

CREATE TABLE IF NOT EXISTS scim_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES sso_providers(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    token_prefix TEXT NOT NULL,
    description TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_scim_tokens_hash
    ON scim_tokens (token_hash);

CREATE INDEX IF NOT EXISTS idx_scim_tokens_provider
    ON scim_tokens (provider_id);
