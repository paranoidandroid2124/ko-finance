-- Migration: create alert_rules and alert_deliveries tables
-- Applies to PostgreSQL

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_status') THEN
        CREATE TYPE alert_status AS ENUM ('active', 'paused', 'archived');
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_delivery_status') THEN
        CREATE TYPE alert_delivery_status AS ENUM ('queued', 'delivered', 'failed', 'throttled', 'skipped');
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS alert_rules (
    id UUID PRIMARY KEY,
    user_id UUID NULL,
    org_id UUID NULL,
    plan_tier VARCHAR(32) NOT NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT NULL,
    status alert_status NOT NULL DEFAULT 'active',
    condition JSONB NOT NULL DEFAULT '{}'::jsonb,
    channels JSONB NOT NULL DEFAULT '[]'::jsonb,
    message_template TEXT NULL,
    evaluation_interval_minutes INTEGER NOT NULL DEFAULT 5,
    window_minutes INTEGER NOT NULL DEFAULT 60,
    cooldown_minutes INTEGER NOT NULL DEFAULT 60,
    max_triggers_per_day INTEGER NULL,
    last_triggered_at TIMESTAMPTZ NULL,
    last_evaluated_at TIMESTAMPTZ NULL,
    throttle_until TIMESTAMPTZ NULL,
    error_count INTEGER NOT NULL DEFAULT 0,
    extras JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_alert_rules_user_id ON alert_rules (user_id);
CREATE INDEX IF NOT EXISTS ix_alert_rules_org_id ON alert_rules (org_id);
CREATE INDEX IF NOT EXISTS ix_alert_rules_plan_tier ON alert_rules (plan_tier);
CREATE INDEX IF NOT EXISTS ix_alert_rules_status ON alert_rules (status);
CREATE INDEX IF NOT EXISTS ix_alert_rules_created_at ON alert_rules (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_alert_rules_last_triggered_at ON alert_rules (last_triggered_at DESC);

CREATE TABLE IF NOT EXISTS alert_deliveries (
    id UUID PRIMARY KEY,
    alert_id UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    channel VARCHAR(32) NOT NULL,
    status alert_delivery_status NOT NULL DEFAULT 'queued',
    message TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_alert_deliveries_alert_id ON alert_deliveries (alert_id);
CREATE INDEX IF NOT EXISTS ix_alert_deliveries_status ON alert_deliveries (status);
CREATE INDEX IF NOT EXISTS ix_alert_deliveries_channel ON alert_deliveries (channel);
CREATE INDEX IF NOT EXISTS ix_alert_deliveries_created_at ON alert_deliveries (created_at DESC);
