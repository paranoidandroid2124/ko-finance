ALTER TABLE event_summary
    ADD COLUMN IF NOT EXISTS cap_bucket TEXT DEFAULT 'ALL';

ALTER TABLE event_summary
    DROP CONSTRAINT IF EXISTS event_summary_pkey;

ALTER TABLE event_summary
    ADD CONSTRAINT event_summary_pkey PRIMARY KEY (asof, event_type, "window", scope, cap_bucket);
