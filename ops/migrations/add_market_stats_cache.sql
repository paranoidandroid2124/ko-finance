-- Precomputed percentile cache for market/grouped metrics

CREATE TABLE IF NOT EXISTS market_stats_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment TEXT NOT NULL,
    segment_value TEXT NOT NULL,
    metric TEXT NOT NULL,
    percentile NUMERIC NOT NULL,
    value NUMERIC,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_market_stats_cache_segment ON market_stats_cache (segment, segment_value, metric);
CREATE INDEX IF NOT EXISTS idx_market_stats_cache_computed_at ON market_stats_cache (computed_at DESC);
