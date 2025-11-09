-- Security metadata reference table and event cap columns

CREATE TABLE IF NOT EXISTS security_metadata (
    ticker TEXT PRIMARY KEY,
    corp_code TEXT,
    corp_name TEXT,
    market TEXT,
    shares BIGINT,
    market_cap NUMERIC,
    cap_bucket TEXT,
    extra JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_security_metadata_market ON security_metadata (market);
CREATE INDEX IF NOT EXISTS idx_security_metadata_cap_bucket ON security_metadata (cap_bucket);

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS market_cap NUMERIC,
    ADD COLUMN IF NOT EXISTS cap_bucket TEXT;

CREATE INDEX IF NOT EXISTS idx_events_cap_bucket ON events (cap_bucket);
