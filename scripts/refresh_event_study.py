"""CLI helper for running the event-study refresh pipeline without Celery."""

from __future__ import annotations

import argparse
import json
import logging
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any, Dict

from scripts._path import add_root

add_root()

from core.env_utils import load_dotenv_if_available  # noqa: E402

load_dotenv_if_available()

from database import SessionLocal  # noqa: E402
from services import event_study_service, security_metadata_service  # noqa: E402

logger = logging.getLogger(__name__)


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _refresh_security_metadata(days_back: int) -> Dict[str, Any]:
    as_of = date.today() - timedelta(days=max(days_back - 1, 0))
    logger.info("Refreshing security metadata (as_of=%s)...", as_of)
    with session_scope() as db:
        rows = security_metadata_service.sync_security_metadata(db, as_of=as_of)
        events_updated = security_metadata_service.backfill_event_cap_metadata(db)
    return {"as_of": as_of.isoformat(), "rows": rows, "events_updated": events_updated}


def _ingest_events(days_back: int) -> Dict[str, Any]:
    end_date = date.today()
    start_date = end_date - timedelta(days=max(days_back, 0))
    logger.info("Ingesting events from filings (%s -> %s)...", start_date, end_date)
    with session_scope() as db:
        created = event_study_service.ingest_events_from_filings(
            db,
            start_date=start_date,
            end_date=end_date,
        )
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "events": created,
    }


def _update_returns() -> Dict[str, Any]:
    logger.info("Updating AR/CAR series for pending events...")
    with session_scope() as db:
        rows = event_study_service.update_event_study_series(db)
    return {"rows": rows}


def _aggregate_summary(as_of: date) -> Dict[str, Any]:
    logger.info("Aggregating event-study summaries (as_of=%s)...", as_of)
    with session_scope() as db:
        summaries = event_study_service.aggregate_event_summaries(db, as_of=as_of)
    return {"as_of": as_of.isoformat(), "summaries": summaries}


def _positive_int(value: str) -> int:
    ivalue = int(value)
    if ivalue < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return ivalue


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the event-study maintenance pipeline once.",
    )
    parser.add_argument(
        "--metadata-days-back",
        type=_positive_int,
        default=1,
        help="Days back when picking the security metadata snapshot (default: 1).",
    )
    parser.add_argument(
        "--event-days-back",
        type=_positive_int,
        default=3,
        help="How many days of filings to convert into events (default: 3).",
    )
    parser.add_argument(
        "--summary-as-of",
        type=str,
        default=None,
        help="Override the summary as-of date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument("--skip-security", action="store_true", help="Skip the security metadata step.")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip the event ingestion step.")
    parser.add_argument("--skip-returns", action="store_true", help="Skip the AR/CAR recomputation step.")
    parser.add_argument("--skip-summary", action="store_true", help="Skip the summary aggregation step.")
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print the final summary as JSON without the friendly log line.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Python logging level (default: INFO).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    summary_as_of = date.today()
    if args.summary_as_of:
        summary_as_of = date.fromisoformat(args.summary_as_of)

    results: Dict[str, Any] = {}

    if not args.skip_security:
        results["security_metadata"] = _refresh_security_metadata(args.metadata_days_back)

    if not args.skip_ingest:
        results["event_ingest"] = _ingest_events(args.event_days_back)

    if not args.skip_returns:
        results["returns"] = _update_returns()

    if not args.skip_summary:
        results["summary"] = _aggregate_summary(summary_as_of)

    payload = json.dumps(results, ensure_ascii=False, indent=2)
    if not args.json_only:
        logger.info("Event-study refresh complete.")
    print(payload)


if __name__ == "__main__":
    main()
