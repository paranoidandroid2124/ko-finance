-- Migration: create digest snapshots table

CREATE TABLE IF NOT EXISTS digest_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    digest_date DATE NOT NULL,
    timeframe VARCHAR(16) NOT NULL DEFAULT 'daily',
    channel VARCHAR(32) NOT NULL DEFAULT 'dashboard',
    user_id UUID NULL,
    org_id UUID NULL,
    payload JSONB NOT NULL,
    llm_model VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_digest_snapshots_scope
    ON digest_snapshots (digest_date, timeframe, channel, user_id, org_id);

CREATE INDEX IF NOT EXISTS ix_digest_snapshots_user_date
    ON digest_snapshots (user_id, digest_date DESC);

CREATE INDEX IF NOT EXISTS ix_digest_snapshots_org_date
    ON digest_snapshots (org_id, digest_date DESC);

COMMENT ON TABLE digest_snapshots IS 'Stored digest payloads for dashboard/email previews.';
