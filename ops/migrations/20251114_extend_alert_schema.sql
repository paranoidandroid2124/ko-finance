-- Migration: extend alert rule and delivery schema for richer telemetry

ALTER TABLE alert_rules
    ADD COLUMN IF NOT EXISTS trigger_type TEXT NOT NULL DEFAULT 'filing',
    ADD COLUMN IF NOT EXISTS filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS state JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS channel_failures JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_alert_rules_trigger_type
    ON alert_rules (trigger_type);

ALTER TABLE alert_deliveries
    ADD COLUMN IF NOT EXISTS event_ref JSONB,
    ADD COLUMN IF NOT EXISTS trigger_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_alert_deliveries_trigger_hash
    ON alert_deliveries (trigger_hash);
