-- Event watchlist configuration for dynamic symbol management

CREATE TABLE IF NOT EXISTS event_watchlist (
    id BIGSERIAL PRIMARY KEY,
    corp_code TEXT,
    ticker TEXT,
    corp_name TEXT,
    market TEXT,
    symbol_type TEXT NOT NULL DEFAULT 'stock',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    extra_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_event_watchlist_symbol
    ON event_watchlist (ticker, symbol_type)
    WHERE ticker IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_event_watchlist_type_enabled
    ON event_watchlist (symbol_type, enabled);
