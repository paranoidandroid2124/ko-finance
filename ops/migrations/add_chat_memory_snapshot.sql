-- Migration: add memory snapshot column for chat sessions
-- Applies to PostgreSQL

ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS memory_snapshot JSONB NULL;

