-- Table Extraction v1 schema: table meta data + cell-level payloads

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS table_meta (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    receipt_no TEXT NULL,
    corp_code TEXT NULL,
    corp_name TEXT NULL,
    ticker TEXT NULL,
    table_type TEXT NOT NULL,
    table_title TEXT NULL,
    page_number INTEGER NULL,
    table_index INTEGER NULL,
    header_rows INTEGER NOT NULL DEFAULT 1,
    row_count INTEGER NOT NULL DEFAULT 0,
    column_count INTEGER NOT NULL DEFAULT 0,
    non_empty_cells INTEGER NOT NULL DEFAULT 0,
    confidence DOUBLE PRECISION NULL,
    latency_ms INTEGER NULL,
    checksum TEXT NULL,
    column_headers JSONB NULL,
    quality JSONB NULL,
    table_json JSONB NULL,
    html TEXT NULL,
    csv TEXT NULL,
    extra JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_table_meta_filing_id ON table_meta(filing_id);
CREATE INDEX IF NOT EXISTS idx_table_meta_receipt_no ON table_meta(receipt_no);
CREATE INDEX IF NOT EXISTS idx_table_meta_type ON table_meta(table_type);
CREATE INDEX IF NOT EXISTS idx_table_meta_created_at ON table_meta(created_at);

CREATE OR REPLACE FUNCTION touch_table_meta_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_table_meta_updated_at ON table_meta;
CREATE TRIGGER trg_table_meta_updated_at
BEFORE UPDATE ON table_meta
FOR EACH ROW
EXECUTE FUNCTION touch_table_meta_updated_at();

CREATE TABLE IF NOT EXISTS table_cells (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_id UUID NOT NULL REFERENCES table_meta(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    column_index INTEGER NOT NULL,
    header_path JSONB NULL,
    raw_value TEXT NULL,
    normalized_value TEXT NULL,
    numeric_value NUMERIC NULL,
    value_type TEXT NULL,
    confidence DOUBLE PRECISION NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_table_cells_table_id ON table_cells(table_id);
CREATE INDEX IF NOT EXISTS idx_table_cells_value_type ON table_cells(value_type);
