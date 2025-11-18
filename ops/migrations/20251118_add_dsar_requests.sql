-- Migration: add dsar_requests table

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE IF NOT EXISTS dsar_request_type AS ENUM ('export', 'delete');
CREATE TYPE IF NOT EXISTS dsar_request_status AS ENUM ('pending', 'processing', 'completed', 'failed');

CREATE TABLE IF NOT EXISTS dsar_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NULL,
    user_id UUID NULL,
    request_type dsar_request_type NOT NULL,
    status dsar_request_status NOT NULL DEFAULT 'pending',
    channel TEXT NOT NULL DEFAULT 'self_service',
    requested_by UUID NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    artifact_path TEXT NULL,
    failure_reason TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_dsar_requests_status_requested_at
    ON dsar_requests (status, requested_at);

CREATE INDEX IF NOT EXISTS idx_dsar_requests_user
    ON dsar_requests (user_id);

CREATE INDEX IF NOT EXISTS idx_dsar_requests_org
    ON dsar_requests (org_id);
