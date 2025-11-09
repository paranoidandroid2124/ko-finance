-- Migration: add email/password auth tables and columns

-- Ensure pgcrypto is available for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Extend users table with auth-related columns
ALTER TABLE "users"
    ADD COLUMN IF NOT EXISTS password_hash TEXT,
    ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS signup_channel TEXT NOT NULL DEFAULT 'email'
        CHECK (signup_channel IN ('email','google','kakao','naver','admin_invite')),
    ADD COLUMN IF NOT EXISTS failed_attempts SMALLINT NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_login_ip INET,
    ADD COLUMN IF NOT EXISTS password_updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS mfa_enrolled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS mfa_secret BYTEA,
    ADD CONSTRAINT chk_users_mfa_consistency CHECK (mfa_secret IS NULL OR mfa_enrolled IS TRUE);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_key
    ON "users" (LOWER(email));

CREATE INDEX IF NOT EXISTS idx_users_email_verified
    ON "users" ((email_verified_at IS NOT NULL));

CREATE INDEX IF NOT EXISTS idx_users_locked_until
    ON "users" (locked_until) WHERE locked_until IS NOT NULL;

-- Magic token storage (email verification, password reset, etc.)
CREATE TABLE IF NOT EXISTS auth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "users"(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    token_type TEXT NOT NULL CHECK (token_type IN ('email_verify','password_reset','email_change','account_unlock')),
    identifier TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_auth_tokens_hash
    ON auth_tokens (token_hash);

CREATE INDEX IF NOT EXISTS idx_auth_tokens_identifier
    ON auth_tokens (identifier);

-- Session / refresh token tracking
CREATE TABLE IF NOT EXISTS session_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "users"(id) ON DELETE CASCADE,
    session_token TEXT NOT NULL,
    refresh_jti TEXT NOT NULL,
    device_label TEXT,
    ip INET,
    user_agent_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_session_tokens_token
    ON session_tokens (session_token);

CREATE INDEX IF NOT EXISTS idx_session_tokens_user
    ON session_tokens (user_id);

CREATE INDEX IF NOT EXISTS idx_session_tokens_refresh
    ON session_tokens (refresh_jti);

-- Audit log for auth events
CREATE TABLE IF NOT EXISTS audit_auth_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES "users"(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    ip INET,
    user_agent TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_auth_events_user
    ON audit_auth_events (user_id);

CREATE INDEX IF NOT EXISTS idx_audit_auth_events_event
    ON audit_auth_events (event_type);
