-- Create table to store Toss webhook audit logs
CREATE TABLE IF NOT EXISTS payments_toss_webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transmission_id TEXT,
    order_id TEXT,
    event_type TEXT,
    status TEXT,
    result TEXT NOT NULL,
    dedupe_key TEXT,
    retry_count INTEGER,
    message TEXT,
    context JSONB,
    payload JSONB,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_toss_webhook_events_transmission_id
    ON payments_toss_webhook_events (transmission_id);

CREATE INDEX IF NOT EXISTS idx_toss_webhook_events_order_id
    ON payments_toss_webhook_events (order_id);

CREATE INDEX IF NOT EXISTS idx_toss_webhook_events_event_type
    ON payments_toss_webhook_events (event_type);

CREATE INDEX IF NOT EXISTS idx_toss_webhook_events_result
    ON payments_toss_webhook_events (result);

CREATE INDEX IF NOT EXISTS idx_toss_webhook_events_dedupe_key
    ON payments_toss_webhook_events (dedupe_key);

CREATE INDEX IF NOT EXISTS idx_toss_webhook_events_created_at
    ON payments_toss_webhook_events (created_at DESC);
