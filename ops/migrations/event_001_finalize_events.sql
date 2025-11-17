-- Ensure events table has the final set of columns for the event study pipeline

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS domain TEXT,
    ADD COLUMN IF NOT EXISTS subtype TEXT,
    ADD COLUMN IF NOT EXISTS confidence NUMERIC,
    ADD COLUMN IF NOT EXISTS is_negative BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_restatement BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS matches JSONB,
    ADD COLUMN IF NOT EXISTS metadata JSONB;

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS market_cap NUMERIC,
    ADD COLUMN IF NOT EXISTS cap_bucket TEXT;

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS source_url TEXT;

CREATE INDEX IF NOT EXISTS idx_events_event_date ON events (event_date);
CREATE INDEX IF NOT EXISTS idx_events_event_type_created_at ON events (event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_ticker_cap_bucket ON events (ticker, cap_bucket);

