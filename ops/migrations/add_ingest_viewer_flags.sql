-- Allows selectively disabling the DART viewer scraper on a corp_code basis.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS ingest_viewer_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    corp_code TEXT NOT NULL UNIQUE,
    fallback_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    reason TEXT NULL,
    updated_by TEXT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingest_viewer_flags_enabled
    ON ingest_viewer_flags (fallback_enabled);
