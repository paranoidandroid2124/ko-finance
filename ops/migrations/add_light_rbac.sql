-- Light RBAC core schema (orgs, roles, memberships) with shadow-mode support hooks

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------------
-- Role catalog
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS org_roles (
    key TEXT PRIMARY KEY,
    rank INTEGER NOT NULL,
    description TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO org_roles (key, rank, description)
VALUES
    ('viewer', 10, 'Read-only access'),
    ('editor', 20, 'May edit alerts/reports'),
    ('admin', 30, 'Full organisation administration')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE FUNCTION touch_org_roles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_org_roles_updated_at ON org_roles;
CREATE TRIGGER trg_org_roles_updated_at
BEFORE UPDATE ON org_roles
FOR EACH ROW
EXECUTE FUNCTION touch_org_roles_updated_at();

-- ------------------------------------------------------------------
-- Organisations table (canonical org_id referenced across services)
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS orgs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
    default_role TEXT NOT NULL DEFAULT 'viewer' REFERENCES org_roles(key) ON UPDATE CASCADE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_orgs_slug_lower
    ON orgs (LOWER(slug))
    WHERE slug IS NOT NULL;

CREATE OR REPLACE FUNCTION touch_orgs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_orgs_updated_at ON orgs;
CREATE TRIGGER trg_orgs_updated_at
BEFORE UPDATE ON orgs
FOR EACH ROW
EXECUTE FUNCTION touch_orgs_updated_at();

-- ------------------------------------------------------------------
-- Upgrade legacy user_org_members -> user_orgs with richer metadata
-- ------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'user_org_members'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'user_orgs'
    ) THEN
        EXECUTE 'ALTER TABLE user_org_members RENAME TO user_orgs';
    END IF;
EXCEPTION WHEN duplicate_table THEN
    NULL;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_orgs' AND column_name = 'role'
    ) THEN
        EXECUTE 'ALTER TABLE user_orgs RENAME COLUMN role TO role_key';
    END IF;
EXCEPTION WHEN undefined_column THEN
    NULL;
END $$;

CREATE TABLE IF NOT EXISTS user_orgs (
    org_id UUID NOT NULL,
    user_id UUID NOT NULL,
    role_key TEXT NOT NULL DEFAULT 'viewer',
    status TEXT NOT NULL DEFAULT 'active',
    invited_by UUID NULL,
    invited_at TIMESTAMPTZ NULL,
    accepted_at TIMESTAMPTZ NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, user_id)
);

ALTER TABLE user_orgs
    ADD COLUMN IF NOT EXISTS invited_by UUID NULL,
    ADD COLUMN IF NOT EXISTS invited_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';

ALTER TABLE user_orgs
    ALTER COLUMN role_key SET NOT NULL,
    ALTER COLUMN status SET NOT NULL,
    ALTER COLUMN metadata SET DEFAULT '{}'::jsonb,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET DEFAULT NOW();

ALTER TABLE user_orgs
    DROP CONSTRAINT IF EXISTS chk_user_orgs_status;

ALTER TABLE user_orgs
    ADD CONSTRAINT chk_user_orgs_status
    CHECK (status IN ('active', 'pending', 'revoked'));

ALTER TABLE user_orgs
    DROP CONSTRAINT IF EXISTS user_org_members_pkey;

ALTER TABLE user_orgs
    DROP CONSTRAINT IF EXISTS pk_user_orgs;

ALTER TABLE user_orgs
    ADD CONSTRAINT pk_user_orgs PRIMARY KEY (org_id, user_id);

ALTER TABLE user_orgs
    DROP CONSTRAINT IF EXISTS fk_user_orgs_org;

ALTER TABLE user_orgs
    ADD CONSTRAINT fk_user_orgs_org
        FOREIGN KEY (org_id) REFERENCES orgs(id) ON DELETE CASCADE;

ALTER TABLE user_orgs
    DROP CONSTRAINT IF EXISTS fk_user_orgs_user;

ALTER TABLE user_orgs
    ADD CONSTRAINT fk_user_orgs_user
        FOREIGN KEY (user_id) REFERENCES "users"(id) ON DELETE CASCADE;

ALTER TABLE user_orgs
    DROP CONSTRAINT IF EXISTS fk_user_orgs_role;

ALTER TABLE user_orgs
    ADD CONSTRAINT fk_user_orgs_role
        FOREIGN KEY (role_key) REFERENCES org_roles(key) ON UPDATE CASCADE;

ALTER TABLE user_orgs
    DROP CONSTRAINT IF EXISTS fk_user_orgs_invited_by;

ALTER TABLE user_orgs
    ADD CONSTRAINT fk_user_orgs_invited_by
        FOREIGN KEY (invited_by) REFERENCES "users"(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_user_orgs_user_status
    ON user_orgs (user_id, status);

CREATE INDEX IF NOT EXISTS idx_user_orgs_org_role
    ON user_orgs (org_id, role_key);

CREATE OR REPLACE FUNCTION touch_user_orgs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_org_members_updated_at ON user_orgs;
DROP FUNCTION IF EXISTS touch_user_org_members_updated_at();
DROP TRIGGER IF EXISTS trg_user_orgs_updated_at ON user_orgs;
CREATE TRIGGER trg_user_orgs_updated_at
BEFORE UPDATE ON user_orgs
FOR EACH ROW
EXECUTE FUNCTION touch_user_orgs_updated_at();

-- ------------------------------------------------------------------
-- Backfill canonical org rows for existing subscriptions/memberships
-- ------------------------------------------------------------------

INSERT INTO orgs (id, name, slug, status)
SELECT DISTINCT org_id,
       'Org ' || LEFT(org_id::text, 8) AS name,
       LOWER(LEFT(org_id::text, 12)) AS slug,
       'active'
FROM (
    SELECT org_id FROM org_subscriptions
    UNION
    SELECT org_id FROM user_orgs
) existing
WHERE org_id IS NOT NULL
ON CONFLICT (id) DO NOTHING;

ALTER TABLE org_subscriptions
    ADD CONSTRAINT fk_org_subscriptions_org
        FOREIGN KEY (org_id) REFERENCES orgs(id) ON DELETE CASCADE;

-- ------------------------------------------------------------------
-- Shadow mode instrumentation helpers (RBAC_ENFORCE env toggles)
-- ------------------------------------------------------------------

COMMENT ON TABLE orgs IS 'Canonical organisation registry used by Entitlement/RBAC services.';
COMMENT ON TABLE org_roles IS 'Role catalog for Light RBAC (viewer/editor/admin).';
COMMENT ON TABLE user_orgs IS 'User memberships per organisation with invite metadata.';
