-- Hybrid search support: add FTS + trigram indexes for filings and news.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE filings
    ADD COLUMN IF NOT EXISTS search_tsv tsvector
        GENERATED ALWAYS AS (
            to_tsvector(
                'simple',
                coalesce(title, '') || ' ' ||
                coalesce(report_name, '') || ' ' ||
                coalesce(corp_name, '') || ' ' ||
                coalesce(raw_md, '')
            )
        ) STORED;

CREATE INDEX IF NOT EXISTS idx_filings_search_tsv ON filings USING GIN (search_tsv);
CREATE INDEX IF NOT EXISTS idx_filings_title_trgm ON filings USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_filings_report_trgm ON filings USING GIN (report_name gin_trgm_ops);

ALTER TABLE news_signals
    ADD COLUMN IF NOT EXISTS search_tsv tsvector
        GENERATED ALWAYS AS (
            to_tsvector(
                'simple',
                coalesce(headline, '') || ' ' ||
                coalesce(summary, '')
            )
        ) STORED;

CREATE INDEX IF NOT EXISTS idx_news_signals_search_tsv ON news_signals USING GIN (search_tsv);
CREATE INDEX IF NOT EXISTS idx_news_signals_headline_trgm ON news_signals USING GIN (headline gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_news_signals_summary_trgm ON news_signals USING GIN (summary gin_trgm_ops);

