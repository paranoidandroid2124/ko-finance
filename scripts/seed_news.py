import argparse
import logging
from typing import List

from scripts._path import add_root

add_root()

from ingest.news_client import MockNewsClient
from ingest.news_fetcher import fetch_news_batch
from parse.tasks import process_news_article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _dispatch_articles(articles: List):
    for article in articles:
        try:
            payload = article.model_dump() if hasattr(article, "model_dump") else article.dict()
            process_news_article.delay(payload)
            logger.info("Queued news article for Celery processing: '%s'", article.headline)
        except Exception as exc:
            logger.error("Failed to enqueue article '%s': %s", article.headline, exc, exc_info=True)


def seed_news(use_mock: bool = False, limit: int = 5):
    """Fetch news (real feed or mock) and enqueue Celery processing tasks."""
    try:
        if use_mock:
            logger.info("Using MockNewsClient as requested.")
            articles = MockNewsClient().fetch_news(limit=limit)
        else:
            articles = fetch_news_batch(limit_per_feed=limit, use_mock_fallback=False)
            if articles:
                logger.info("Fetched %d article(s) from live feeds.", len(articles))
            else:
                logger.warning("No live feed articles available from configured sources.")

        if not articles:
            logger.warning("No news articles fetched. Nothing to enqueue.")
            return

        _dispatch_articles(articles)
        logger.info("Dispatched %d article(s) to Celery.", len(articles))
    except Exception as exc:
        logger.error("Unexpected error during news seeding: %s", exc, exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed news articles into the processing pipeline.")
    parser.add_argument("--use-mock", action="store_true", help="Force using the mock news client.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of articles per feed.")
    args = parser.parse_args()
    seed_news(use_mock=args.use_mock, limit=args.limit)
