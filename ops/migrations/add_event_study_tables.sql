-- Event study support tables (events, prices, event_study, event_summary)

CREATE TABLE IF NOT EXISTS events (
    rcept_no TEXT PRIMARY KEY,
    corp_code TEXT NOT NULL,
    ticker TEXT,
    corp_name TEXT,
    event_type TEXT NOT NULL,
    event_date DATE,
    amount NUMERIC,
    ratio NUMERIC,
    shares BIGINT,
    start_date DATE,
    end_date DATE,
    method TEXT,
    score NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events (created_at DESC);


CREATE TABLE IF NOT EXISTS prices (
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    adj_close NUMERIC,
    volume BIGINT,
    ret NUMERIC,
    benchmark BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_prices_benchmark ON prices (benchmark);


CREATE TABLE IF NOT EXISTS event_study (
    rcept_no TEXT NOT NULL,
    t SMALLINT NOT NULL,
    ar NUMERIC,
    car NUMERIC,
    PRIMARY KEY (rcept_no, t),
    CONSTRAINT fk_event_study_event
        FOREIGN KEY (rcept_no) REFERENCES events (rcept_no)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_event_study_t ON event_study (t);


CREATE TABLE IF NOT EXISTS event_summary (
    asof DATE NOT NULL,
    event_type TEXT NOT NULL,
    window TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'market',
    filters JSONB,
    n INTEGER NOT NULL,
    aar JSONB,
    caar JSONB,
    hit_rate NUMERIC,
    mean_caar NUMERIC,
    ci_lo NUMERIC,
    ci_hi NUMERIC,
    p_value NUMERIC,
    dist JSONB,
    PRIMARY KEY (asof, event_type, window, scope)
);

CREATE INDEX IF NOT EXISTS idx_event_summary_event_type ON event_summary (event_type);
