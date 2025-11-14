-- Migration: asynchronous RAG grid job stores

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS rag_grid_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL CHECK (status IN ('pending','running','completed','failed')),
    trace_id TEXT,
    requested_by UUID,
    ticker_count INTEGER NOT NULL,
    question_count INTEGER NOT NULL,
    total_cells INTEGER NOT NULL,
    completed_cells INTEGER NOT NULL DEFAULT 0,
    failed_cells INTEGER NOT NULL DEFAULT 0,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag_grid_cells (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES rag_grid_jobs(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    question TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','running','ok','error')),
    latency_ms INTEGER,
    answer TEXT,
    evidence JSONB,
    warnings JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_grid_cells_job ON rag_grid_cells(job_id);

COMMENT ON TABLE rag_grid_jobs IS 'Tracks long running QA grid jobs.';
COMMENT ON TABLE rag_grid_cells IS 'Stores per-cell results for QA grids.';
