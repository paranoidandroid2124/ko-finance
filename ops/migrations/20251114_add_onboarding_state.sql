-- Add onboarding tracking columns to users table
ALTER TABLE "users"
    ADD COLUMN IF NOT EXISTS first_login_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS onboarded_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS onboarding_checklist JSONB NOT NULL DEFAULT '{}'::jsonb;
