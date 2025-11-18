
"\"\"\"Backfill DE002~DE005 data for existing filings.\"\"\""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta

from scripts._path import add_root

add_root()

from database import SessionLocal
from ingest.dart_client import DartClient
from models.filing import Filing
from services.dart_sync import sync_additional_disclosures

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def backfill_disclosures(days_back: int | None = None, ticker: str | None = None) -> int:
    """Re-run DE002~DE005 sync for filings already stored in the database."""
    session = SessionLocal()
    processed = 0

    try:
        query = session.query(Filing)
        if ticker:
            query = query.filter(Filing.ticker == ticker)
        if days_back:
            since = datetime.now() - timedelta(days=days_back)
            query = query.filter(Filing.filed_at >= since)

        query = query.order_by(Filing.filed_at.desc().nullslast(), Filing.created_at.desc())

        client = DartClient()
        for filing in query:
            receipt_no = getattr(filing, "receipt_no", None)
            if not receipt_no:
                continue
            try:
                sync_additional_disclosures(db=session, client=client, filing=filing)
                processed += 1
                if processed % 50 == 0:
                    session.commit()
                    logger.info("Processed %s filings so far...", processed)
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.warning("Failed to sync filing %s (%s): %s", receipt_no, getattr(filing, "corp_name", ""), exc, exc_info=True)

        session.commit()
        logger.info("Backfill complete. Synced %s filings.", processed)
        return processed
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill DE002~DE005 data for stored filings.")
    parser.add_argument("--days-back", type=int, default=None, help="Only process filings filed within N days.")
    parser.add_argument("--ticker", type=str, default=None, help="Restrict backfill to a specific ticker.")
    args = parser.parse_args()

    backfill_disclosures(days_back=args.days_back, ticker=args.ticker)
