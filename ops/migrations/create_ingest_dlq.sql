-- Dead-letter queue table for ingest Celery tasks

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ingest_dlq_status') THEN
        CREATE TYPE ingest_dlq_status AS ENUM ('pending', 'requeued', 'completed');
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS ingest_dead_letters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name TEXT NOT NULL,
    receipt_no TEXT NULL,
    corp_code TEXT NULL,
    ticker TEXT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT NOT NULL,
    retries INTEGER NOT NULL DEFAULT 0,
    status ingest_dlq_status NOT NULL DEFAULT 'pending',
    next_run_at TIMESTAMPTZ NULL,
    last_error_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE ingest_dead_letters
    DROP CONSTRAINT IF EXISTS chk_ingest_dead_letters_retries_nonnegative;

ALTER TABLE ingest_dead_letters
    ADD CONSTRAINT chk_ingest_dead_letters_retries_nonnegative
    CHECK (retries >= 0);

CREATE INDEX IF NOT EXISTS idx_ingest_dead_letters_status
    ON ingest_dead_letters (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingest_dead_letters_receipt
    ON ingest_dead_letters (receipt_no);

CREATE INDEX IF NOT EXISTS idx_ingest_dead_letters_task
    ON ingest_dead_letters (task_name);
