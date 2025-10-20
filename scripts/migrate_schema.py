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


def migrate_schema() -> None:
    logger.info("Starting schema migration for K-Finance data tables.")
    _add_columns()
    logger.info("Schema migration completed successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_schema()
