-- Seed initial event watchlist entries for core KOSPI names and benchmark ETFs.

INSERT INTO event_watchlist (corp_code, ticker, corp_name, market, symbol_type, extra_metadata, enabled)
VALUES
    (NULL, '005930', '삼성전자', 'KOSPI', 'stock', '{"priority": 1}', TRUE),
    (NULL, '000660', 'SK하이닉스', 'KOSPI', 'stock', '{"priority": 1}', TRUE),
    (NULL, '035720', '카카오', 'KOSPI', 'stock', '{"priority": 2}', TRUE),
    (NULL, '035420', 'NAVER', 'KOSPI', 'stock', '{"priority": 2}', TRUE),
    (NULL, '069500', 'KODEX 200 ETF', 'KOSPI', 'benchmark', '{"description": "KOSPI200 tracking ETF"}', TRUE)
ON CONFLICT (ticker, symbol_type)
DO UPDATE SET
    corp_code = COALESCE(EXCLUDED.corp_code, event_watchlist.corp_code),
    corp_name = COALESCE(EXCLUDED.corp_name, event_watchlist.corp_name),
    market = COALESCE(EXCLUDED.market, event_watchlist.market),
    extra_metadata = COALESCE(EXCLUDED.extra_metadata, event_watchlist.extra_metadata),
    enabled = EXCLUDED.enabled,
    updated_at = now();

