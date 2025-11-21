-- Migration: create table for proactive notification feed
CREATE TABLE IF NOT EXISTS proactive_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    ticker TEXT NULL,
    title TEXT NULL,
    summary TEXT NULL,
    target_url TEXT NULL,
    status TEXT NOT NULL DEFAULT 'unread',
    metadata JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_proactive_user_source UNIQUE (user_id, source_type, source_id)
);

CREATE INDEX IF NOT EXISTS ix_proactive_notifications_user_created_at
    ON proactive_notifications (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_proactive_notifications_status
    ON proactive_notifications (status);
