BEGIN;

DROP TABLE IF EXISTS session_activity;
DROP TABLE IF EXISTS session_tokens;
DROP TABLE IF EXISTS auth_tokens;
DROP TABLE IF EXISTS audit_auth_events;

DROP INDEX IF EXISTS idx_auth_tokens_lookup;
DROP INDEX IF EXISTS idx_session_tokens_user_active;
DROP INDEX IF EXISTS idx_session_tokens_refresh_jti;
DROP INDEX IF EXISTS idx_session_activity_session;
DROP INDEX IF EXISTS idx_session_activity_created_at;
DROP INDEX IF EXISTS idx_audit_auth_events_user;
DROP INDEX IF EXISTS idx_audit_auth_events_event_type;
DROP INDEX IF EXISTS idx_audit_auth_events_created_at;
DROP INDEX IF EXISTS idx_users_email_verified;
DROP INDEX IF EXISTS idx_users_locked_until;
DROP INDEX IF EXISTS users_email_lower_key;

ALTER TABLE "users"
    DROP CONSTRAINT IF EXISTS chk_mfa_consistency;

ALTER TABLE "users"
    DROP COLUMN IF EXISTS mfa_secret,
    DROP COLUMN IF EXISTS mfa_enrolled,
    DROP COLUMN IF EXISTS password_updated_at,
    DROP COLUMN IF EXISTS last_login_ip,
    DROP COLUMN IF EXISTS locked_until,
    DROP COLUMN IF EXISTS failed_attempts,
    DROP COLUMN IF EXISTS signup_channel,
    DROP COLUMN IF EXISTS email_verified_at,
    DROP COLUMN IF EXISTS password_hash;

COMMIT;
