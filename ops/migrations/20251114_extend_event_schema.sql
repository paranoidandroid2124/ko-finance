-- Extend events table with extraction metadata and add event alert linkage tables

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS domain TEXT,
    ADD COLUMN IF NOT EXISTS subtype TEXT,
    ADD COLUMN IF NOT EXISTS confidence NUMERIC,
    ADD COLUMN IF NOT EXISTS is_negative BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_restatement BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS matches JSONB,
    ADD COLUMN IF NOT EXISTS metadata JSONB;

CREATE INDEX IF NOT EXISTS idx_events_domain ON events (domain);
CREATE INDEX IF NOT EXISTS idx_events_ticker_event_type ON events (ticker, event_type);


CREATE TABLE IF NOT EXISTS event_alert_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id TEXT NOT NULL REFERENCES events (rcept_no) ON DELETE CASCADE,
    alert_id UUID NOT NULL REFERENCES alert_rules (id) ON DELETE CASCADE,
    match_score NUMERIC,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    matched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, alert_id)
);

CREATE INDEX IF NOT EXISTS idx_event_alert_matches_alert_id
    ON event_alert_matches (alert_id);


CREATE TABLE IF NOT EXISTS event_ingest_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    events_created INTEGER NOT NULL DEFAULT 0,
    events_skipped INTEGER NOT NULL DEFAULT 0,
    errors JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_event_ingest_jobs_status
    ON event_ingest_jobs (status, window_start, window_end);
