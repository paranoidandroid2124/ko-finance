-- AuditLog v1 schema with monthly partitions

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id UUID NULL,
    org_id UUID NULL,
    action TEXT NOT NULL,
    target_id TEXT NULL,
    source TEXT NOT NULL,
    ua TEXT NULL,
    ip_hash TEXT NULL,
    feature_flags JSONB NULL,
    extra JSONB NULL,
    CONSTRAINT pk_audit_logs PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'audit_logs_default'
            AND n.nspname = 'public'
    ) THEN
        EXECUTE '
            CREATE TABLE audit_logs_default
            PARTITION OF audit_logs DEFAULT
        ';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_audit_logs_org_ts
    ON audit_logs USING BRIN (org_id, ts);

CREATE INDEX IF NOT EXISTS idx_audit_logs_action_ts
    ON audit_logs (action, ts DESC);
