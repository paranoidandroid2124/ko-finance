-- Align event_summary schema with the new pipeline outputs

ALTER TABLE event_summary
    ALTER COLUMN scope SET DEFAULT 'market';

ALTER TABLE event_summary
    ALTER COLUMN cap_bucket SET DEFAULT 'ALL';

ALTER TABLE event_summary
    ALTER COLUMN n TYPE BIGINT USING n::bigint;

CREATE INDEX IF NOT EXISTS idx_event_summary_cap_bucket ON event_summary (cap_bucket);
CREATE INDEX IF NOT EXISTS idx_event_summary_scope_window ON event_summary (scope, window);

