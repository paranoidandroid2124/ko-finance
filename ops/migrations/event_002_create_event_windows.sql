-- Canonical event window presets shared by the backend and UI

CREATE TABLE IF NOT EXISTS event_windows (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT,
    start_offset SMALLINT NOT NULL,
    end_offset SMALLINT NOT NULL,
    default_significance NUMERIC NOT NULL DEFAULT 0.1,
    display_order SMALLINT NOT NULL DEFAULT 0,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO event_windows (key, label, description, start_offset, end_offset, default_significance, display_order, is_default)
VALUES
    ('window_short', '[-5,+5]', 'Short reaction window for quick disclosures', -5, 5, 0.1, 10, FALSE),
    ('window_medium', '[-5,+20]', 'Default drift window used by dashboards', -5, 20, 0.1, 20, TRUE),
    ('window_long', '[-10,+30]', 'Extended observation window for structural events', -10, 30, 0.1, 30, FALSE)
ON CONFLICT (key) DO UPDATE SET
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    start_offset = EXCLUDED.start_offset,
    end_offset = EXCLUDED.end_offset,
    default_significance = EXCLUDED.default_significance,
    display_order = EXCLUDED.display_order,
    is_default = EXCLUDED.is_default,
    updated_at = now();

