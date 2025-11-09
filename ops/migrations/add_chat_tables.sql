-- Migration: create chat session persistence tables
-- Applies to PostgreSQL

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'chat_message_state') THEN
        CREATE TYPE chat_message_state AS ENUM ('pending', 'streaming', 'ready', 'error');
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NULL,
    org_id UUID NULL,
    title VARCHAR(255) NOT NULL DEFAULT '새 대화',
    summary TEXT NULL,
    context_type VARCHAR(64) NULL,
    context_id VARCHAR(128) NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    token_budget INTEGER NULL,
    summary_tokens INTEGER NULL,
    last_message_at TIMESTAMPTZ NULL,
    last_read_at TIMESTAMPTZ NULL,
    archived_at TIMESTAMPTZ NULL,
    version BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_id ON chat_sessions (user_id);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_org_id ON chat_sessions (org_id);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_context ON chat_sessions (context_type, context_id);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_last_message ON chat_sessions (last_message_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_archived_at ON chat_sessions (archived_at);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    turn_id UUID NOT NULL,
    retry_of_message_id UUID NULL REFERENCES chat_messages(id),
    reply_to_message_id UUID NULL REFERENCES chat_messages(id),
    role VARCHAR(32) NOT NULL,
    state chat_message_state NOT NULL DEFAULT 'pending',
    error_code VARCHAR(64) NULL,
    error_message TEXT NULL,
    content TEXT NULL,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key VARCHAR(128) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_chat_messages_session_seq UNIQUE (session_id, seq),
    CONSTRAINT uq_chat_messages_idempotency_key UNIQUE (idempotency_key)
);

CREATE INDEX IF NOT EXISTS ix_chat_messages_session ON chat_messages (session_id);
CREATE INDEX IF NOT EXISTS ix_chat_messages_turn ON chat_messages (turn_id);
CREATE INDEX IF NOT EXISTS ix_chat_messages_retry ON chat_messages (retry_of_message_id);
CREATE INDEX IF NOT EXISTS ix_chat_messages_reply ON chat_messages (reply_to_message_id);
CREATE INDEX IF NOT EXISTS ix_chat_messages_role ON chat_messages (role);
CREATE INDEX IF NOT EXISTS ix_chat_messages_state ON chat_messages (state);
CREATE INDEX IF NOT EXISTS ix_chat_messages_created_at ON chat_messages (created_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages_archive (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    seq INTEGER NOT NULL,
    payload JSONB NOT NULL,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chat_messages_archive_session ON chat_messages_archive (session_id);
CREATE INDEX IF NOT EXISTS ix_chat_messages_archive_archived_at ON chat_messages_archive (archived_at DESC);

CREATE TABLE IF NOT EXISTS chat_audit (
    id UUID PRIMARY KEY,
    session_id UUID NULL,
    message_id UUID NULL,
    actor_id UUID NULL,
    action VARCHAR(64) NOT NULL,
    metadata JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chat_audit_session ON chat_audit (session_id);
CREATE INDEX IF NOT EXISTS ix_chat_audit_message ON chat_audit (message_id);
CREATE INDEX IF NOT EXISTS ix_chat_audit_actor ON chat_audit (actor_id);
CREATE INDEX IF NOT EXISTS ix_chat_audit_created_at ON chat_audit (created_at DESC);
