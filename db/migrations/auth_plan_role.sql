ALTER TABLE "users"
    ADD COLUMN IF NOT EXISTS plan_tier TEXT NOT NULL DEFAULT 'free' CHECK (plan_tier IN ('free','pro','enterprise')),
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin')),
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
-- Optionally seed admin role manually after running this migration.
