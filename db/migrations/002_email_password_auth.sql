BEGIN;

-- 1. users table hardening for credential auth
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
    ADD COLUMN IF NOT EXISTS mfa_secret BYTEA;

ALTER TABLE "users"
    ADD CONSTRAINT IF NOT EXISTS chk_mfa_consistency
    CHECK (mfa_secret IS NULL OR mfa_enrolled IS TRUE);

-- backfill email verification timestamp from legacy column if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'emailVerified'
    ) THEN
        EXECUTE '
            UPDATE "users"
            SET email_verified_at = COALESCE(email_verified_at, "emailVerified")
            WHERE "emailVerified" IS NOT NULL;
        ';
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_key
    ON "users" (LOWER(email));

CREATE INDEX IF NOT EXISTS idx_users_email_verified
    ON "users" ((email_verified_at IS NOT NULL));

CREATE INDEX IF NOT EXISTS idx_users_locked_until
    ON "users" (locked_until)
    WHERE locked_until IS NOT NULL;

-- derive signup channel for existing social accounts
WITH ranked_accounts AS (
    SELECT
        "userId" AS user_id,
        LOWER(provider) AS provider,
        ROW_NUMBER() OVER (PARTITION BY "userId" ORDER BY id) AS rn
    FROM accounts
)
UPDATE "users" u
SET signup_channel = CASE
        WHEN ra.provider IN ('google','kakao','naver') THEN ra.provider
        ELSE signup_channel
    END
FROM ranked_accounts ra
WHERE ra.user_id = u.id
  AND ra.rn = 1;

-- 2. auth_tokens table for email verification & password reset links
CREATE TABLE IF NOT EXISTS auth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "users"(id) ON DELETE CASCADE,
    token TEXT UNIQUE,
    token_hash TEXT UNIQUE,
    token_type TEXT NOT NULL CHECK (token_type IN ('email_verify','password_reset','email_change','account_unlock')),
    identifier TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (token IS NOT NULL OR token_hash IS NOT NULL),
    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_auth_tokens_lookup
    ON auth_tokens (token_type, COALESCE(token, token_hash))
    WHERE used_at IS NULL AND expires_at > NOW();

-- 3. session_tokens table for refresh-token tracking
CREATE TABLE IF NOT EXISTS session_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "users"(id) ON DELETE CASCADE,
    session_token TEXT NOT NULL UNIQUE,
    refresh_jti UUID NOT NULL UNIQUE,
    device_label TEXT,
    ip INET,
    user_agent_hash TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_session_tokens_user_active
    ON session_tokens (user_id)
    WHERE revoked_at IS NULL AND expires_at > NOW();

CREATE INDEX IF NOT EXISTS idx_session_tokens_refresh_jti
    ON session_tokens (refresh_jti);

-- optional per-session activity log
CREATE TABLE IF NOT EXISTS session_activity (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES session_tokens(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('login','refresh','logout','unlock','mfa_challenge')),
    ip INET,
    user_agent TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_activity_session
    ON session_activity (session_id);

CREATE INDEX IF NOT EXISTS idx_session_activity_created_at
    ON session_activity (created_at DESC);

-- 4. audit log for auth events
CREATE TABLE IF NOT EXISTS audit_auth_events (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES "users"(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'register','login_success','login_failed','password_reset_request',
        'password_reset','email_verify','lock','unlock','mfa_challenge'
    )),
    channel TEXT NOT NULL DEFAULT 'email',
    ip INET,
    user_agent TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_auth_events_user
    ON audit_auth_events (user_id);

CREATE INDEX IF NOT EXISTS idx_audit_auth_events_event_type
    ON audit_auth_events (event_type);

CREATE INDEX IF NOT EXISTS idx_audit_auth_events_created_at
    ON audit_auth_events (created_at DESC);

COMMIT;
