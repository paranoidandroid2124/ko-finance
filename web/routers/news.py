"""FastAPI routes exposing Market Mood data."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.news import NewsObservation, NewsSignal
from schemas.api.news import (
    NewsInsightsResponse,
    NewsListItem,
    NewsObservationResponse,
    NewsSignalResponse,
    NewsTopicInsight,
)
from services.aggregation.sector_classifier import (
    DEFAULT_SECTOR_SLUG,
    SECTOR_DEFINITIONS,
    resolve_sector_slug,
)
from services.news_summary_service import get_or_generate_summary
from web.routers.dashboard import format_timespan, map_sentiment

router = APIRouter(prefix="/news", tags=["News"])


def _sector_name_from_slug(slug: str) -> str:
    return SECTOR_DEFINITIONS.get(slug, SECTOR_DEFINITIONS[DEFAULT_SECTOR_SLUG])


def _normalize_topic(value: str) -> str:
    return value.strip().lower()




def _build_news_insights(
    db: Session,
    *,
    limit: int = 12,
    sectors: List[str] | None = None,
    negative_only: bool = False,
    exclude_neutral: bool = False,
    window_hours: int = 24,
) -> NewsInsightsResponse:
    now = datetime.now(timezone.utc)
    window_hours = max(1, min(window_hours, 24 * 30))
    window_start = now - timedelta(hours=window_hours)

    candidate_news = (
        db.query(NewsSignal)
        .filter(NewsSignal.published_at <= now)
        .filter(NewsSignal.published_at >= window_start)
        .order_by(NewsSignal.published_at.desc())
        .limit(500)
        .all()
    )

    requested_sectors = {sector.strip() for sector in (sectors or []) if sector.strip()}

    news_items: List[NewsListItem] = []
    filtered_signals: List[tuple[NewsSignal, str, str]] = []

    for entry in candidate_news:
        body_text = entry.summary
        evidence = getattr(entry, "evidence", None)
        if not body_text and isinstance(evidence, dict):
            body_text = evidence.get("rationale")
        slug = resolve_sector_slug(entry.topics, entry.ticker, title=entry.headline, body=body_text)
        sector = _sector_name_from_slug(slug)
        sentiment_label = map_sentiment(entry.sentiment)

        if requested_sectors and (slug not in requested_sectors) and (sector not in requested_sectors):
            continue
        if negative_only and sentiment_label != "negative":
            continue
        if exclude_neutral and sentiment_label == "neutral":
            continue

        filtered_signals.append((entry, sector, sentiment_label))
        if len(news_items) < limit:
            summary_text = get_or_generate_summary(entry)
            news_items.append(
                NewsListItem(
                    id=entry.id,
                    title=entry.headline,
                    sentiment=sentiment_label,
                    source=entry.source,
                    publishedAt=format_timespan(entry.published_at),
                    sector=sector,
                    sentimentScore=entry.sentiment,
                    publishedAtIso=entry.published_at.isoformat() if entry.published_at else "",
                    url=entry.url,
                    summary=summary_text,
                    licenseType=getattr(entry, "license_type", None),
                    licenseUrl=getattr(entry, "license_url", None),
                )
            )

    topic_counts: Counter[str] = Counter()
    topic_sentiments: Dict[str, List[float]] = defaultdict(list)
    topic_labels: Dict[str, str] = {}
    topic_top_articles: Dict[str, NewsSignal] = {}

    for entry, _, _ in filtered_signals:
        if not entry.topics:
            continue
        for topic in entry.topics:
            if not isinstance(topic, str) or not topic.strip():
                continue
            normalized = _normalize_topic(topic)
            topic_counts[normalized] += 1
            topic_labels.setdefault(normalized, topic)
            if entry.sentiment is not None:
                topic_sentiments[normalized].append(float(entry.sentiment))
            if normalized not in topic_top_articles:
                topic_top_articles[normalized] = entry

    top_topics = topic_counts.most_common(5)
    topics: List[NewsTopicInsight] = []
    for normalized, count in top_topics:
        scores = topic_sentiments.get(normalized, [])
        avg_score = sum(scores) / len(scores) if scores else 0.0
        article = topic_top_articles.get(normalized)
        top_article_id = article.id if article else None
        top_article_title = article.headline if article else None
        top_article_url = article.url if article else None
        top_article_source = article.source if article else None
        top_article_published = (
            format_timespan(article.published_at) if article and article.published_at else None
        )
        topics.append(
            NewsTopicInsight(
                name=topic_labels.get(normalized, normalized),
                change=f"{count}건",
                sentiment=map_sentiment(avg_score),
                topArticleId=top_article_id,
                topArticleTitle=top_article_title,
                topArticleUrl=top_article_url,
                topArticleSource=top_article_source,
                topArticlePublishedAt=top_article_published,
            )
        )

    return NewsInsightsResponse(news=news_items, topics=topics)


@router.get("/", response_model=List[NewsSignalResponse])
def list_news_signals(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """Return paginated news sentiment signals."""
    news_signals = (
        db.query(NewsSignal)
        .order_by(NewsSignal.published_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return news_signals


@router.get("/observations", response_model=List[NewsObservationResponse])
def list_news_observations(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """Return aggregated Market Mood observations."""
    observations = (
        db.query(NewsObservation)
        .order_by(NewsObservation.window_start.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return observations


@router.get("/insights", response_model=NewsInsightsResponse)
def read_news_insights(
    limit: int = 12,
    sectors: List[str] = Query(default_factory=list),
    negative_only: bool = Query(False),
    exclude_neutral: bool = Query(False),
    window_hours: int = Query(24),
    db: Session = Depends(get_db),
) -> NewsInsightsResponse:
    return _build_news_insights(
        db,
        limit=limit,
        sectors=sectors or None,
        negative_only=negative_only,
        exclude_neutral=exclude_neutral,
        window_hours=window_hours,
    )
