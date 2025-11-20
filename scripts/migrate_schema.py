import logging

from sqlalchemy import inspect, text

from database import engine

logger = logging.getLogger(__name__)


def _execute(statement: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(statement))


def _has_column(table: str, column: str) -> bool:
    inspector = inspect(engine)
    return any(col["name"] == column for col in inspector.get_columns(table))


def _rename_column_if_needed(table: str, old: str, new: str) -> None:
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns(table)}
    if old in columns and new not in columns:
        logger.info("Renaming %s.%s -> %s", table, old, new)
        _execute(f'ALTER TABLE {table} RENAME COLUMN "{old}" TO "{new}";')


def _drop_column_if_exists(table: str, column: str) -> None:
    logger.info("Dropping column if exists: %s.%s", table, column)
    _execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{column}";')


def _ensure_news_observations_table() -> None:
    logger.info("Ensuring news_observations table exists.")
    _execute(
        """
        CREATE TABLE IF NOT EXISTS news_observations (
            id UUID PRIMARY KEY,
            window_start TIMESTAMPTZ NOT NULL UNIQUE,
            window_end TIMESTAMPTZ NOT NULL,
            article_count INTEGER NOT NULL DEFAULT 0,
            positive_count INTEGER NOT NULL DEFAULT 0,
            neutral_count INTEGER NOT NULL DEFAULT 0,
            negative_count INTEGER NOT NULL DEFAULT 0,
            avg_sentiment DOUBLE PRECISION,
            min_sentiment DOUBLE PRECISION,
            max_sentiment DOUBLE PRECISION,
            top_topics JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    _execute(
        """
        CREATE INDEX IF NOT EXISTS idx_news_observations_window_start
            ON news_observations(window_start);
        """
    )


def _ensure_eval_runs_table() -> None:
    logger.info("Ensuring eval_runs table exists.")
    _execute(
        """
        CREATE TABLE IF NOT EXISTS eval_runs (
            id UUID PRIMARY KEY,
            ts TIMESTAMPTZ DEFAULT NOW(),
            suite TEXT NOT NULL,
            pipeline_version TEXT,
            metrics JSONB NOT NULL
        );
        """
    )
    _execute(
        """
        CREATE INDEX IF NOT EXISTS idx_eval_runs_ts ON eval_runs(ts);
        """
    )


def _ensure_sector_tables() -> None:
    logger.info("Ensuring sector metrics tables exist.")
    _execute(
        """
        CREATE TABLE IF NOT EXISTS sectors (
            id SERIAL PRIMARY KEY,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    _execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sectors_slug ON sectors(slug);
        """
    )
    _execute(
        """
        CREATE TABLE IF NOT EXISTS news_article_sectors (
            article_id UUID NOT NULL REFERENCES news_signals(id) ON DELETE CASCADE,
            sector_id INT NOT NULL REFERENCES sectors(id) ON DELETE CASCADE,
            weight DOUBLE PRECISION DEFAULT 1.0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (article_id, sector_id)
        );
        """
    )
    _execute(
        """
        CREATE INDEX IF NOT EXISTS idx_news_article_sectors_sector
            ON news_article_sectors(sector_id);
        """
    )
    _execute(
        """
        CREATE TABLE IF NOT EXISTS sector_daily_metrics (
            sector_id INT NOT NULL REFERENCES sectors(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            sent_mean DOUBLE PRECISION,
            sent_std DOUBLE PRECISION,
            volume INTEGER,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (sector_id, date)
        );
        """
    )
    _execute(
        """
        CREATE TABLE IF NOT EXISTS sector_window_metrics (
            sector_id INT NOT NULL REFERENCES sectors(id) ON DELETE CASCADE,
            window_days SMALLINT NOT NULL,
            asof_date DATE NOT NULL,
            sent_mean DOUBLE PRECISION,
            vol_sum INTEGER,
            sent_z DOUBLE PRECISION,
            vol_z DOUBLE PRECISION,
            delta_sent_7d DOUBLE PRECISION,
            top_article_id UUID REFERENCES news_signals(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (sector_id, window_days, asof_date)
        );
        """
    )
    _execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sector_window_metrics_sector
            ON sector_window_metrics(sector_id);
        """
    )
    _execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sector_window_metrics_top_article
            ON sector_window_metrics(top_article_id);
        """
    )


def _ensure_evidence_snapshots_table() -> None:
    logger.info("Ensuring evidence_snapshots table exists.")
    _execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_snapshots (
            urn_id TEXT NOT NULL,
            snapshot_hash TEXT NOT NULL,
            previous_snapshot_hash TEXT,
            diff_type TEXT DEFAULT 'unknown',
            payload JSONB NOT NULL,
            author TEXT,
            process TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (urn_id, snapshot_hash)
        );
        """
    )
    _execute(
        """
        CREATE INDEX IF NOT EXISTS idx_evidence_snapshots_urn
            ON evidence_snapshots(urn_id);
        """
    )
    _execute(
        """
        CREATE INDEX IF NOT EXISTS idx_evidence_snapshots_updated_at
            ON evidence_snapshots(updated_at DESC);
        """
    )

def _add_columns() -> None:
    logger.info("Ensuring filings table columns are up to date.")
    filings_columns = [
        '"corp_name" TEXT',
        '"market" TEXT',
        '"report_name" TEXT',
        '"file_name" TEXT',
        '"file_path" TEXT',
        '"category" TEXT',
        '"category_confidence" DOUBLE PRECISION',
        '"notes" TEXT',
        '"analysis_status" TEXT DEFAULT \'PENDING\'',
        '"created_at" TIMESTAMPTZ DEFAULT NOW()',
        '"updated_at" TIMESTAMPTZ DEFAULT NOW()',
    ]

    for column_def in filings_columns:
        _execute(f"ALTER TABLE filings ADD COLUMN IF NOT EXISTS {column_def};")

    _execute('ALTER TABLE filings ADD COLUMN IF NOT EXISTS "urls" JSONB;')
    _execute('ALTER TABLE filings ADD COLUMN IF NOT EXISTS "source_files" JSONB;')
    _execute('ALTER TABLE filings ADD COLUMN IF NOT EXISTS "raw_md" TEXT;')
    _execute('ALTER TABLE filings ADD COLUMN IF NOT EXISTS "chunks" JSONB;')
    _execute('ALTER TABLE filings ALTER COLUMN "status" SET DEFAULT \'PENDING\';')
    if _has_column("filings", "analysis_status"):
        _execute('ALTER TABLE filings ALTER COLUMN "analysis_status" SET DEFAULT \'PENDING\';')
    else:
        _execute('ALTER TABLE filings ADD COLUMN IF NOT EXISTS "analysis_status" TEXT DEFAULT \'PENDING\';')
    _execute("UPDATE filings SET analysis_status = 'PENDING' WHERE analysis_status IS NULL;")

    logger.info("Updating extracted_facts columns.")
    _rename_column_if_needed("extracted_facts", "key", "fact_type")

    facts_columns = [
        '"unit" TEXT',
        '"currency" TEXT',
        '"anchor_page" INTEGER',
        '"anchor_quote" TEXT',
        '"anchor" JSONB',
        '"method" TEXT DEFAULT \'llm_extraction\'',
        '"confidence_score" DOUBLE PRECISION',
        '"notes" TEXT',
        '"created_at" TIMESTAMPTZ DEFAULT NOW()',
        '"updated_at" TIMESTAMPTZ DEFAULT NOW()',
    ]
    for column_def in facts_columns:
        _execute(f"ALTER TABLE extracted_facts ADD COLUMN IF NOT EXISTS {column_def};")
    _execute("UPDATE extracted_facts SET method = 'llm_extraction' WHERE method IS NULL;")

    logger.info("Ensuring summaries table columns.")
    summary_columns = [
        '"who" TEXT',
        '"what" TEXT',
        '"when" TEXT',
        '"where" TEXT',
        '"how" TEXT',
        '"why" TEXT',
        '"insight" TEXT',
        '"confidence_score" DOUBLE PRECISION',
        '"sentiment_label" TEXT',
        '"sentiment_reason" TEXT',
        '"created_at" TIMESTAMPTZ DEFAULT NOW()',
        '"updated_at" TIMESTAMPTZ DEFAULT NOW()',
    ]
    for column_def in summary_columns:
        _execute(f"ALTER TABLE summaries ADD COLUMN IF NOT EXISTS {column_def};")

    if _has_column("summaries", "fiveW1H"):
        logger.info("Migrating legacy fiveW1H JSON data into discrete columns.")
        _execute(
            """
            UPDATE summaries
            SET
                who = COALESCE(who, ("fiveW1H"->>'who')),
                what = COALESCE(what, ("fiveW1H"->>'what')),
                "when" = COALESCE("when", ("fiveW1H"->>'when')),
                "where" = COALESCE("where", ("fiveW1H"->>'where')),
                how = COALESCE(how, ("fiveW1H"->>'how')),
                why = COALESCE(why, ("fiveW1H"->>'why'))
            WHERE "fiveW1H" IS NOT NULL;
            """
        )

    if _has_column("summaries", "faithfulness"):
        logger.info("Migrating legacy faithfulness score into confidence_score.")
        _execute(
            """
            UPDATE summaries
            SET confidence_score = COALESCE(confidence_score, faithfulness)
            WHERE faithfulness IS NOT NULL;
            """
        )

    # Legacy summary schema clean-up for superseded columns
    for legacy_column in ("fiveW1H", "faithfulness"):
        _drop_column_if_exists("summaries", legacy_column)

    _ensure_news_observations_table()
    _ensure_eval_runs_table()
    _ensure_sector_tables()
    _ensure_evidence_snapshots_table()

    logger.info("Ensuring reliability columns on news tables.")
    _execute('ALTER TABLE news_signals ADD COLUMN IF NOT EXISTS "source_reliability" DOUBLE PRECISION;')
    _execute('ALTER TABLE news_window_aggregates ADD COLUMN IF NOT EXISTS "source_reliability" DOUBLE PRECISION;')
    logger.info("Ensuring news license metadata columns.")
    _execute('ALTER TABLE news_signals ADD COLUMN IF NOT EXISTS "license_type" TEXT;')
    _execute('ALTER TABLE news_signals ADD COLUMN IF NOT EXISTS "license_url" TEXT;')


def migrate_schema() -> None:
    logger.info("Starting schema migration for Nuvien data tables.")
    _add_columns()
    logger.info("Schema migration completed successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_schema()
