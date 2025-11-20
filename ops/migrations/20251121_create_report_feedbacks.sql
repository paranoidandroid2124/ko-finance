CREATE TABLE IF NOT EXISTS report_feedbacks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('LIKE', 'DISLIKE')),
    category TEXT,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_feedbacks_report ON report_feedbacks (report_id);
CREATE INDEX IF NOT EXISTS idx_report_feedbacks_user ON report_feedbacks (user_id);
