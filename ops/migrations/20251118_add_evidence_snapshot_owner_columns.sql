-- Track tenant ownership for evidence snapshots to enforce workspace isolation.

ALTER TABLE evidence_snapshots
    ADD COLUMN IF NOT EXISTS org_id UUID NULL,
    ADD COLUMN IF NOT EXISTS user_id UUID NULL;

CREATE INDEX IF NOT EXISTS idx_evidence_snapshots_org_id
    ON evidence_snapshots (org_id);

CREATE INDEX IF NOT EXISTS idx_evidence_snapshots_user_id
    ON evidence_snapshots (user_id);

-- Backfill user identifiers from author metadata when the value looks like a UUID.
WITH candidate_rows AS (
    SELECT urn_id, snapshot_hash, author
    FROM evidence_snapshots
    WHERE user_id IS NULL
      AND author ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
)
UPDATE evidence_snapshots AS es
SET user_id = cr.author::uuid
FROM candidate_rows AS cr
WHERE es.urn_id = cr.urn_id
  AND es.snapshot_hash = cr.snapshot_hash;
