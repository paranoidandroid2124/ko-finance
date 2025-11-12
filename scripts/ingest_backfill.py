"""CLI helper to backfill DART filings over a date range."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import date, datetime, timedelta
from typing import Iterator, Tuple

from scripts._path import add_root

add_root()

from core.env_utils import load_dotenv_if_available  # noqa: E402

load_dotenv_if_available()

from database import SessionLocal  # noqa: E402
from ingest.dart_seed import seed_recent_filings  # noqa: E402
from services.ingest_metrics import observe_backfill_duration  # noqa: E402

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc


def _chunk_range(start: date, end: date, chunk_days: int) -> Iterator[Tuple[date, date]]:
    if chunk_days <= 0:
        raise argparse.ArgumentTypeError("--chunk-days must be positive.")
    cursor = start
    delta = timedelta(days=chunk_days - 1)
    while cursor <= end:
        chunk_end = min(end, cursor + delta)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill DART filings with idempotent upserts.")
    parser.add_argument("--start-date", type=_parse_date, required=True, help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", type=_parse_date, required=True, help="Inclusive end date (YYYY-MM-DD).")
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=3,
        help="Number of days to fetch per seeding chunk (default: 3).",
    )
    parser.add_argument("--corp-code", type=str, default=None, help="Restrict backfill to a specific corp_code.")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO).")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    start_date = min(args.start_date, args.end_date)
    end_date = max(args.start_date, args.end_date)
    total_inserted = 0
    started = time.perf_counter()

    db = SessionLocal()
    try:
        for chunk_start, chunk_end in _chunk_range(start_date, end_date, max(1, args.chunk_days)):
            logger.info(
                "Backfilling filings %s -> %s (corp_code=%s)",
                chunk_start,
                chunk_end,
                args.corp_code or "ALL",
            )
            created = seed_recent_filings(
                db=db,
                start_date=chunk_start,
                end_date=chunk_end,
                corp_code=args.corp_code,
            )
            total_inserted += created
    finally:
        db.close()

    duration = time.perf_counter() - started
    observe_backfill_duration(duration)
    logger.info(
        "Backfill completed: %d filings inserted in %.2f seconds (range %s -> %s).",
        total_inserted,
        duration,
        start_date,
        end_date,
    )


if __name__ == "__main__":
    main()
