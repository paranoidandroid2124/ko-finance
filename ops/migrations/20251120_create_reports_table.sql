CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID REFERENCES orgs(id) ON DELETE SET NULL,
    ticker VARCHAR(32) NOT NULL,
    title TEXT,
    content_md TEXT NOT NULL,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_user ON reports (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_org ON reports (org_id, created_at DESC);
