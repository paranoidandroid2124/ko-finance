import logging
import time
from pathlib import Path
from typing import Callable, Iterable

from scripts._path import add_root

add_root()

from sqlalchemy.exc import OperationalError

from database import Base, engine
from models.company import CorpMetric, FilingEvent, InsiderTransaction  # noqa: F401
from models.fact import ExtractedFact  # noqa: F401
from models.filing import Filing  # noqa: F401
from models.news import NewsObservation, NewsSignal, NewsWindowAggregate  # noqa: F401
from models.sector import (  # noqa: F401
    NewsArticleSector,
    Sector,
    SectorDailyMetric,
    SectorWindowMetric,
)
from models.summary import Summary  # noqa: F401
from scripts.migrate_schema import migrate_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATION_SQL_FILES: Iterable[Path] = (
    Path("db/migrations/auth_core_tables.sql"),
    Path("db/migrations/auth_plan_role.sql"),
    Path("db/migrations/auth_email_password_extension.sql"),
)


def _retry(operation: Callable[[], None], *, retries: int = 7, delay: float = 3.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            operation()
            return
        except OperationalError as exc:
            if attempt == retries:
                raise
            logger.warning(
                "Database not ready yet (attempt %d/%d). Retrying in %.1f seconds: %s",
                attempt,
                retries,
                delay,
                exc,
            )
            time.sleep(delay)


def _load_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff").strip()


def _apply_sql_files() -> None:
    for sql_path in MIGRATION_SQL_FILES:
        if not sql_path.exists():
            logger.warning("SQL migration file %s is missing; skipping.", sql_path)
            continue
        sql = _load_sql(sql_path)
        if not sql:
            logger.info("SQL migration file %s is empty; skipping.", sql_path)
            continue
        logger.info("Applying SQL migration: %s", sql_path)

        def _execute() -> None:
            with engine.begin() as connection:
                connection.exec_driver_sql(sql)

        _retry(_execute)


def init_db() -> None:
    logger.info("Starting database bootstrap.")
    try:
        _apply_sql_files()
        _retry(lambda: Base.metadata.create_all(bind=engine))
        logger.info("SQLAlchemy model tables ensured.")
        migrate_schema()
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc, exc_info=True)


if __name__ == "__main__":
    init_db()
