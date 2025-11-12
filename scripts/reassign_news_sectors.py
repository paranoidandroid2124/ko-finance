"""Re-run sector assignment for stored NewsSignal rows."""

from __future__ import annotations

import argparse
import logging
from typing import Optional

from scripts._path import add_root

add_root()

from database import SessionLocal  # noqa: E402
from models.news import NewsSignal  # noqa: E402
from models.sector import NewsArticleSector  # noqa: E402
from services.aggregation.sector_classifier import assign_article_to_sector  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def reassign_sectors(limit: Optional[int] = None, batch_size: int = 200) -> int:
    """Reassign sectors for NewsSignal entries using the latest classifier."""
    session = SessionLocal()
    processed = 0
    try:
        query = session.query(NewsSignal).order_by(NewsSignal.published_at.asc().nullslast(), NewsSignal.created_at.asc())
        if limit:
            query = query.limit(limit)

        for signal in query.yield_per(batch_size):
            try:
                session.query(NewsArticleSector).filter(NewsArticleSector.article_id == signal.id).delete(
                    synchronize_session=False
                )
                assign_article_to_sector(session, signal)
                processed += 1
                if processed % batch_size == 0:
                    session.commit()
                    logger.info("Reassigned %s news signals...", processed)
            except Exception as exc:  # pragma: no cover - defensive guard
                session.rollback()
                logger.warning("Failed to reassign sector for %s (%s): %s", signal.id, signal.headline, exc, exc_info=True)

        session.commit()
        logger.info("Sector reassignment complete for %s news signals.", processed)
        return processed
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reassign sectors for stored news signals.")
    parser.add_argument("--limit", type=int, default=None, help="Reassign at most N news signals.")
    parser.add_argument("--batch-size", type=int, default=200, help="Commit after processing this many rows.")
    args = parser.parse_args()

    reassign_sectors(limit=args.limit, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
