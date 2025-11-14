"""Fetch and normalise news articles from RSS/Atom feeds."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Set
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.env import env_float, env_int, env_str
from core.logging import get_logger
from schemas.news import NewsArticleCreate
from services.kogl_license import detect_kogl_license
from services.ingest_errors import FatalIngestError, TransientIngestError

try:
    import feedparser  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in unit tests
    feedparser = None  # type: ignore[assignment]


logger = get_logger(__name__)
_DEFAULT_USER_AGENT = "KFinanceNewsBot/0.1 (+https://kfinance.ai)"


def _get_request_headers() -> dict:
    user_agent = env_str("NEWS_FEED_USER_AGENT", _DEFAULT_USER_AGENT) or _DEFAULT_USER_AGENT
    return {
        "User-Agent": user_agent,
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    }


def _parse_entry_time(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None) or entry.get(attr)
        if parsed:
            try:
                timestamp = time.mktime(parsed)
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (OverflowError, ValueError, OSError):
                logger.debug("Failed to convert %s for entry %s.", attr, entry, exc_info=True)
    return datetime.now(timezone.utc)


def _join_entry_content(entry) -> str:
    parts: List[str] = []
    title = entry.get("title")
    summary = entry.get("summary") or entry.get("description")
    if title:
        parts.append(str(title))
    if summary:
        parts.append(str(summary))

    for section in entry.get("content") or []:
        value = section.get("value")
        if value:
            parts.append(str(value))

    return "\n\n".join(part.strip() for part in parts if part and str(part).strip())


def _extract_license_metadata(entry, feed_meta) -> tuple[Optional[str], Optional[str]]:
    license_url: Optional[str] = None
    links = entry.get("links") or []
    for link in links:
        if isinstance(link, dict) and link.get("rel") == "license":
            license_url = link.get("href") or license_url
            if license_url:
                break

    license_text_candidates = [
        entry.get("rights"),
        entry.get("dc_rights"),
        entry.get("license"),
        entry.get("kogl"),
    ]
    if isinstance(feed_meta, dict):
        license_text_candidates.extend(
            [
                feed_meta.get("rights"),
                feed_meta.get("license"),
            ]
        )

    license_text = next(
        (candidate for candidate in license_text_candidates if isinstance(candidate, str) and candidate.strip()),
        None,
    )
    return detect_kogl_license(license_text, license_url=license_url)


def _entry_to_article(entry, source_name: str, feed_meta) -> NewsArticleCreate:
    link = entry.get("link") or ""
    summary = entry.get("summary") or entry.get("description")
    published_at = _parse_entry_time(entry)
    original_text = _join_entry_content(entry) or (summary or "")
    license_type, license_url = _extract_license_metadata(entry, feed_meta)

    return NewsArticleCreate(
        ticker=None,
        source=source_name,
        url=link,
        headline=entry.get("title") or "Untitled news",
        summary=summary,
        published_at=published_at,
        original_text=original_text or link or source_name,
        license_type=license_type,
        license_url=license_url,
    )


def _iter_feed_sources(feed_urls: Iterable[str]) -> Iterable[str]:
    for raw in feed_urls:
        url = raw.strip()
        if url:
            yield url


def _load_feed_bytes(feed_url: str) -> bytes:
    request = Request(feed_url, headers=_get_request_headers())
    timeout = env_float("NEWS_FEED_TIMEOUT", 10.0, minimum=1.0)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - controlled allowlist
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise TransientIngestError(f"Failed to download feed {feed_url}") from exc


def _parse_feed_retry(feed_url: str):
    if feedparser is None:
        logger.warning("feedparser is not installed. Skipping feed %s.", feed_url)
        raise FatalIngestError("feedparser dependency is missing.")

    max_attempts = env_int("NEWS_FEED_MAX_ATTEMPTS", 2, minimum=1)
    backoff_base = env_float("NEWS_FEED_RETRY_BACKOFF", 1.5, minimum=0.5)
    sleep_cap = env_float("NEWS_FEED_RETRY_MAX_SLEEP", 5.0, minimum=0.5)
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            raw_bytes = _load_feed_bytes(feed_url)
            parsed = feedparser.parse(raw_bytes)
            if getattr(parsed, "bozo", 0):
                logger.warning(
                    "Feed parser reported issues for %s: %s",
                    feed_url,
                    getattr(parsed, "bozo_exception", "unknown error"),
                )
            return parsed
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            logger.warning(
                "Feed fetch attempt %d/%d failed for %s: %s",
                attempt,
                max_attempts,
                feed_url,
                exc,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            last_error = exc
            logger.error("Unexpected error while fetching %s: %s", feed_url, exc, exc_info=True)

        if attempt < max_attempts:
            sleep_seconds = min(backoff_base * attempt, sleep_cap)
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    if last_error:
        logger.error("Feed fetch failed after %d attempts for %s: %s", max_attempts, feed_url, last_error)
        raise TransientIngestError(f"Feed {feed_url} failed after retries.") from last_error
    raise TransientIngestError(f"Feed {feed_url} returned no data.")


def _load_mock_articles(limit: int) -> List[NewsArticleCreate]:
    try:
        from ingest.news_client import MockNewsClient

        logger.info("Falling back to MockNewsClient for news ingestion.")
        client = MockNewsClient()
        return client.fetch_news(limit=limit)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Mock news fallback failed: %s", exc, exc_info=True)
        return []


def fetch_news_batch(limit_per_feed: int = 5, *, use_mock_fallback: bool = False) -> List[NewsArticleCreate]:
    """Fetch latest news articles from configured RSS/Atom feeds."""
    if feedparser is None:
        if use_mock_fallback:
            return _load_mock_articles(limit_per_feed)
        logger.warning("feedparser is not installed and mock fallback is disabled.")
        raise FatalIngestError("feedparser dependency missing for news ingest.")

    env_value = env_str("NEWS_FEEDS", "") or ""
    feed_urls = list(_iter_feed_sources(env_value.split(",")))

    if not feed_urls:
        logger.warning("NEWS_FEEDS is empty.")
        if use_mock_fallback:
            return _load_mock_articles(limit_per_feed)
        raise FatalIngestError("NEWS_FEEDS is empty; cannot ingest news.")

    articles: List[NewsArticleCreate] = []
    seen_keys: Set[str] = set()
    failed_feeds: List[str] = []

    for feed_url in feed_urls:
        try:
            parsed = _parse_feed_retry(feed_url)
        except FatalIngestError:
            raise
        except TransientIngestError as exc:
            failed_feeds.append(feed_url)
            logger.warning("%s", exc)
            continue

        feed_meta = getattr(parsed, "feed", {}) or {}
        if hasattr(feed_meta, "get"):
            source_name = feed_meta.get("title")
        elif isinstance(feed_meta, dict):
            source_name = feed_meta.get("title")
        else:
            source_name = getattr(feed_meta, "title", None)
        if not source_name:
            source_name = feed_url

        entries = (getattr(parsed, "entries", None) or [])[:limit_per_feed]
        logger.info("Fetched %d entries from %s", len(entries), feed_url)

        for entry in entries:
            try:
                article = _entry_to_article(entry, source_name=source_name, feed_meta=feed_meta)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to normalize entry from %s: %s", feed_url, exc, exc_info=True)
                continue

            dedupe_key = article.url or f"{article.headline}-{article.published_at.isoformat()}"
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            articles.append(article)

    if failed_feeds:
        logger.warning("Failed to fetch %d feed(s): %s", len(failed_feeds), ", ".join(failed_feeds))

    if not articles:
        if use_mock_fallback:
            return _load_mock_articles(limit_per_feed)
        if failed_feeds:
            raise TransientIngestError("All configured news feeds failed.")
        raise FatalIngestError("Configured news feeds returned no entries.")

    return articles


__all__ = ["fetch_news_batch"]
