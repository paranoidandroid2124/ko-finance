"""CLI helper to backfill filings, prices, and event-study aggregates over a date range."""

from __future__ import annotations

import argparse
import json
import logging
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Dict, Generator, Tuple

from scripts._path import add_root

add_root()

from core.env_utils import load_dotenv_if_available  # noqa: E402

load_dotenv_if_available()

from database import SessionLocal  # noqa: E402
from ingest.dart_seed import seed_recent_filings  # noqa: E402
from services.event_study_service import (  # noqa: E402
    aggregate_event_summaries,
    ingest_events_from_filings,
    update_event_study_series,
)
from services.market_data_service import (  # noqa: E402
    ingest_etf_prices,
    ingest_stock_prices,
)

logger = logging.getLogger(__name__)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc


def chunked_dates(start: date, end: date, chunk_days: int) -> Generator[Tuple[date, date], None, None]:
    if chunk_days <= 0:
        raise ValueError("chunk_days must be positive")
    cursor = start
    delta = timedelta(days=chunk_days - 1)
    while cursor <= end:
        chunk_end = min(end, cursor + delta)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def backfill_filings_and_events(start: date, end: date, chunk_days: int) -> Dict[str, int]:
    total_filings = 0
    total_events = 0
    with session_scope() as db:
        for chunk_start, chunk_end in chunked_dates(start, end, chunk_days):
            logger.info("Seeding filings %s -> %s", chunk_start, chunk_end)
            created = seed_recent_filings(db=db, start_date=chunk_start, end_date=chunk_end)
            total_filings += created
            logger.info("Ingesting events for %s -> %s", chunk_start, chunk_end)
            ingested = ingest_events_from_filings(db, start_date=chunk_start, end_date=chunk_end)
            total_events += ingested
    return {"filings": total_filings, "events": total_events}


def backfill_prices(start: date, end: date) -> Dict[str, int]:
    with session_scope() as db:
        logger.info("Ingesting stock prices %s -> %s", start, end)
        stocks = ingest_stock_prices(db, start_date=start, end_date=end)
        logger.info("Ingesting benchmark prices %s -> %s", start, end)
        benchmarks = ingest_etf_prices(db, start_date=start, end_date=end)
    return {"stocks": stocks, "benchmarks": benchmarks}


def refresh_event_metrics(as_of: date) -> Dict[str, int]:
    with session_scope() as db:
        logger.info("Updating AR/CAR series…")
        series_rows = update_event_study_series(db)
    with session_scope() as db:
        logger.info("Aggregating summaries (as_of=%s)…", as_of)
        summary_rows = aggregate_event_summaries(db, as_of=as_of)
    return {"series": series_rows, "summaries": summary_rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill filings, prices, and event-study aggregates.")
    parser.add_argument("--start-date", type=parse_date, default=(date.today() - timedelta(days=90)))
    parser.add_argument("--end-date", type=parse_date, default=date.today())
    parser.add_argument("--chunk-days", type=int, default=7, help="Filings ingestion chunk size (days).")
    parser.add_argument(
        "--price-pad-days",
        type=int,
        default=200,
        help="Pad the price ingestion window on both sides for estimation windows.",
    )
    parser.add_argument("--skip-filings", action="store_true", help="Skip DART filings/event ingestion.")
    parser.add_argument("--skip-prices", action="store_true", help="Skip price backfill.")
    parser.add_argument("--skip-metrics", action="store_true", help="Skip AR/CAR + summary refresh.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    start_date = min(args.start_date, args.end_date)
    end_date = max(args.start_date, args.end_date)

    results: Dict[str, Dict[str, int]] = {}

    if not args.skip_filings:
        results["filings"] = backfill_filings_and_events(start_date, end_date, args.chunk_days)

    if not args.skip_prices:
        price_start = start_date - timedelta(days=args.price_pad_days)
        price_end = end_date + timedelta(days=args.price_pad_days)
        results["prices"] = backfill_prices(price_start, price_end)

    if not args.skip_metrics:
        results["metrics"] = refresh_event_metrics(end_date)

    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
