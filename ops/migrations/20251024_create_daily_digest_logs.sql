-- Migration: create daily digest logs table
-- Applies to PostgreSQL

CREATE TABLE IF NOT EXISTS daily_digest_logs (
    id UUID PRIMARY KEY,
    digest_date DATE NOT NULL,
    channel VARCHAR(32) NOT NULL DEFAULT 'telegram',
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_daily_digest_logs UNIQUE (digest_date, channel)
);
