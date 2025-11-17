-- Align event_summary schema with the new pipeline outputs

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'event_summary' AND column_name = 'window'
    ) THEN
        EXECUTE 'ALTER TABLE event_summary RENAME COLUMN "window" TO window_key';
    END IF;
END $$;

ALTER TABLE event_summary
    ALTER COLUMN scope SET DEFAULT 'market';

ALTER TABLE event_summary
    ALTER COLUMN cap_bucket SET DEFAULT 'ALL';

ALTER TABLE event_summary
    ALTER COLUMN n TYPE BIGINT USING n::bigint;

CREATE INDEX IF NOT EXISTS idx_event_summary_cap_bucket ON event_summary (cap_bucket);
CREATE INDEX IF NOT EXISTS idx_event_summary_scope_window ON event_summary (scope, window_key);

