-- Research Notebook v1 schema: notebooks, entries, shares

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS notebooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    owner_id UUID NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NULL,
    tags TEXT[] NOT NULL DEFAULT '{}'::text[],
    cover_color TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    entry_count INTEGER NOT NULL DEFAULT 0,
    last_activity_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notebooks_org_id
    ON notebooks(org_id);

CREATE INDEX IF NOT EXISTS idx_notebooks_tags
    ON notebooks USING GIN (tags);

CREATE OR REPLACE FUNCTION touch_notebooks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notebooks_updated_at ON notebooks;
CREATE TRIGGER trg_notebooks_updated_at
BEFORE UPDATE ON notebooks
FOR EACH ROW
EXECUTE FUNCTION touch_notebooks_updated_at();


CREATE TABLE IF NOT EXISTS notebook_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    author_id UUID NOT NULL,
    highlight TEXT NOT NULL,
    annotation TEXT NULL,
    annotation_format TEXT NOT NULL DEFAULT 'markdown',
    tags TEXT[] NOT NULL DEFAULT '{}'::text[],
    source JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notebook_entries_notebook_id
    ON notebook_entries(notebook_id);

CREATE INDEX IF NOT EXISTS idx_notebook_entries_tags
    ON notebook_entries USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_notebook_entries_position
    ON notebook_entries(notebook_id, position DESC);

CREATE OR REPLACE FUNCTION touch_notebook_entries_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notebook_entries_updated_at ON notebook_entries;
CREATE TRIGGER trg_notebook_entries_updated_at
BEFORE UPDATE ON notebook_entries
FOR EACH ROW
EXECUTE FUNCTION touch_notebook_entries_updated_at();


CREATE TABLE IF NOT EXISTS notebook_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    created_by UUID NOT NULL,
    expires_at TIMESTAMPTZ NULL,
    password_hash TEXT NULL,
    password_hint TEXT NULL,
    access_scope TEXT NOT NULL DEFAULT 'view',
    revoked_at TIMESTAMPTZ NULL,
    last_accessed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notebook_shares_notebook_id
    ON notebook_shares(notebook_id);

CREATE INDEX IF NOT EXISTS idx_notebook_shares_token
    ON notebook_shares(token);

CREATE OR REPLACE FUNCTION touch_notebook_shares_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        NEW.created_at = OLD.created_at;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notebook_shares_updated_at ON notebook_shares;
CREATE TRIGGER trg_notebook_shares_updated_at
BEFORE UPDATE ON notebook_shares
FOR EACH ROW
EXECUTE FUNCTION touch_notebook_shares_updated_at();


CREATE OR REPLACE FUNCTION bump_notebook_activity_on_insert()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE notebooks
    SET entry_count = entry_count + 1,
        last_activity_at = NOW(),
        updated_at = NOW()
    WHERE id = NEW.notebook_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION bump_notebook_activity_on_update()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE notebooks
    SET last_activity_at = NOW(),
        updated_at = NOW()
    WHERE id = NEW.notebook_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION bump_notebook_activity_on_delete()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE notebooks
    SET entry_count = GREATEST(entry_count - 1, 0),
        last_activity_at = NOW(),
        updated_at = NOW()
    WHERE id = OLD.notebook_id;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notebook_entries_after_insert ON notebook_entries;
CREATE TRIGGER trg_notebook_entries_after_insert
AFTER INSERT ON notebook_entries
FOR EACH ROW
EXECUTE FUNCTION bump_notebook_activity_on_insert();

DROP TRIGGER IF EXISTS trg_notebook_entries_after_update ON notebook_entries;
CREATE TRIGGER trg_notebook_entries_after_update
AFTER UPDATE ON notebook_entries
FOR EACH ROW
EXECUTE FUNCTION bump_notebook_activity_on_update();

DROP TRIGGER IF EXISTS trg_notebook_entries_after_delete ON notebook_entries;
CREATE TRIGGER trg_notebook_entries_after_delete
AFTER DELETE ON notebook_entries
FOR EACH ROW
EXECUTE FUNCTION bump_notebook_activity_on_delete();
