"\"\"\"One-shot bootstrap job to seed initial data after containers start.\"\"\""

from __future__ import annotations

import logging
import os

from scripts._path import add_root

add_root()

from ingest.dart_seed import seed_recent_filings
from scripts.seed_news import seed_news

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def seed_bootstrap() -> None:
    """Run initial DART/news seeding when services start."""
    days_back = int(os.getenv("BOOTSTRAP_FILINGS_DAYS_BACK", "3"))
    news_limit = int(os.getenv("BOOTSTRAP_NEWS_LIMIT", "5"))

    logger.info("Bootstrapping data: filings days_back=%s, news_limit=%s", days_back, news_limit)
    try:
        created = seed_recent_filings(days_back=days_back)
        logger.info("Bootstrap filings complete (created=%s).", created)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Bootstrap filings encountered an error: %s", exc)

    try:
        seed_news(use_mock=False, limit=news_limit)
        logger.info("Bootstrap news seeding dispatched.")
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Bootstrap news encountered an error: %s", exc)


if __name__ == "__main__":
    seed_bootstrap()
