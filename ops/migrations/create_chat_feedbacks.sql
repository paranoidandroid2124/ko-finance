CREATE TABLE IF NOT EXISTS chat_feedbacks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    score INTEGER NOT NULL CHECK (score IN (1, -1)),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_feedbacks_message ON chat_feedbacks (message_id);
CREATE INDEX IF NOT EXISTS idx_chat_feedbacks_user ON chat_feedbacks (user_id);
