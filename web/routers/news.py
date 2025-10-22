"""FastAPI routes exposing Market Mood data."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.news import NewsObservation, NewsSignal
from schemas.api.news import (
    NewsInsightsResponse,
    NewsListItem,
    NewsObservationResponse,
    NewsSentimentHeatmapPoint,
    NewsSentimentHeatmapResponse,
    NewsSignalResponse,
    NewsTopicInsight,
)
from web.routers.dashboard import format_timespan, map_sentiment

router = APIRouter(prefix="/news", tags=["News"])

DEFAULT_SECTOR = "기타"
SECTOR_KEYWORDS: Dict[str, List[str]] = {
    "반도체": ["반도체", "semi", "chip", "hbm", "메모리", "memory"],
    "에너지": ["에너지", "energy", "전력", "oil", "gas", "원유"],
    "금융": ["금융", "bank", "은행", "금리", "증권", "보험"],
    "바이오": ["바이오", "bio", "제약", "pharma", "의료", "헬스"],
    "소비재": ["소비", "유통", "리테일", "consumer", "생활", "식품"],
    "모빌리티": ["모빌", "자동차", "car", "전기차", "모빌리티", "모빌"],
}
TICKER_SECTOR_MAP: Dict[str, str] = {
    "005930": "반도체",
    "000660": "반도체",
    "051910": "소비재",
    "035720": "모빌리티",
    "035420": "모빌리티",
    "068270": "바이오",
    "207940": "바이오",
    "096770": "에너지",
}


def _normalize_topic(topic: str) -> str:
    return topic.strip().lower()


def _classify_sector(topics: List[str] | None, ticker: str | None) -> str:
    if topics:
        normalized = [_normalize_topic(topic) for topic in topics if isinstance(topic, str) and topic.strip()]
        for sector, keywords in SECTOR_KEYWORDS.items():
            for keyword in keywords:
                keyword_normalized = keyword.lower()
                if any(keyword_normalized in topic for topic in normalized):
                    return sector

    if ticker:
        return TICKER_SECTOR_MAP.get(ticker, DEFAULT_SECTOR)

    return DEFAULT_SECTOR


def _build_heatmap(
    db: Session,
    *,
    window_minutes: int = 60,
    bucket_minutes: int = 15,
    max_sectors: int = 6,
) -> NewsSentimentHeatmapResponse:
    if window_minutes <= 0:
        window_minutes = 60
    if bucket_minutes <= 0:
        bucket_minutes = 15
    bucket_count = max(1, window_minutes // bucket_minutes + 1)

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=window_minutes + bucket_minutes)

    signals = (
        db.query(NewsSignal)
        .filter(NewsSignal.published_at >= window_start)
        .filter(NewsSignal.published_at <= now)
        .order_by(NewsSignal.published_at.desc())
        .all()
    )

    bucket_ranges: List[tuple[int, str, datetime, datetime]] = []
    for index in range(bucket_count):
        offset = (bucket_count - 1 - index) * bucket_minutes
        bucket_end = now - timedelta(minutes=offset)
        bucket_start = bucket_end - timedelta(minutes=bucket_minutes)
        label = "현재" if offset == 0 else f"-{offset}분"
        bucket_ranges.append((index, label, bucket_start, bucket_end))

    sector_counts: Counter[str] = Counter()
    bucket_values: dict[tuple[str, int], dict[str, object]] = defaultdict(lambda: {"sentiments": [], "count": 0})

    for signal in signals:
        sector = _classify_sector(signal.topics, signal.ticker)
        sector_counts[sector] += 1

        published_at = signal.published_at
        if published_at is None:
            continue
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        for bucket_index, _, bucket_start, bucket_end in bucket_ranges:
            if bucket_start <= published_at <= bucket_end:
                key = (sector, bucket_index)
                bucket_values[key]["count"] = int(bucket_values[key]["count"]) + 1
                if signal.sentiment is not None:
                    sentiments = bucket_values[key]["sentiments"]
                    if isinstance(sentiments, list):
                        sentiments.append(float(signal.sentiment))
                    else:
                        bucket_values[key]["sentiments"] = [float(signal.sentiment)]
                break

    top_sectors = [sector for sector, _ in sector_counts.most_common(max_sectors)]
    if not top_sectors:
        top_sectors = [DEFAULT_SECTOR]

    # Ensure DEFAULT_SECTOR present if data exists but filtered out
    if DEFAULT_SECTOR in sector_counts and DEFAULT_SECTOR not in top_sectors:
        if len(top_sectors) >= max_sectors:
            top_sectors[-1] = DEFAULT_SECTOR
        else:
            top_sectors.append(DEFAULT_SECTOR)

    points: List[NewsSentimentHeatmapPoint] = []
    sector_index_map = {sector: idx for idx, sector in enumerate(top_sectors)}

    for sector, idx in sector_index_map.items():
        for bucket_index, _, _, _ in bucket_ranges:
            key = (sector, bucket_index)
            data = bucket_values.get(key)
            if not data:
                points.append(
                    NewsSentimentHeatmapPoint(
                        sector_index=idx,
                        bucket_index=bucket_index,
                        sentiment=None,
                        article_count=0,
                    )
                )
                continue
            sentiments = data.get("sentiments")
            sentiment_value = None
            if isinstance(sentiments, list) and len(sentiments) > 0:
                sentiment_value = sum(sentiments) / len(sentiments)
            points.append(
                NewsSentimentHeatmapPoint(
                    sector_index=idx,
                    bucket_index=bucket_index,
                    sentiment=round(sentiment_value, 3) if sentiment_value is not None else None,
                    article_count=int(data.get("count", 0)),
                )
            )

    ordered_buckets = [{"label": label, "start": start.isoformat(), "end": end.isoformat()} for (_, label, start, end) in bucket_ranges]
    return NewsSentimentHeatmapResponse(sectors=top_sectors, buckets=ordered_buckets, points=points)


def _build_news_insights(db: Session, *, limit: int = 12) -> NewsInsightsResponse:
    now = datetime.now(timezone.utc)
    recent_news = (
        db.query(NewsSignal)
        .filter(NewsSignal.published_at <= now)
        .order_by(NewsSignal.published_at.desc())
        .limit(limit)
        .all()
    )

    news_items: List[NewsListItem] = []
    for entry in recent_news:
        sentiment_label = map_sentiment(entry.sentiment)
        news_items.append(
            NewsListItem(
                id=entry.id,
                title=entry.headline,
                sentiment=sentiment_label,
                source=entry.source,
                publishedAt=format_timespan(entry.published_at),
            )
        )

    latest_observation = (
        db.query(NewsObservation)
        .order_by(NewsObservation.window_start.desc())
        .first()
    )
    previous_observation = (
        db.query(NewsObservation)
        .filter(NewsObservation.id != (latest_observation.id if latest_observation else None))
        .order_by(NewsObservation.window_start.desc())
        .first()
    )

    previous_topic_counts: Dict[str, int] = {}
    if previous_observation and previous_observation.top_topics:
        for item in previous_observation.top_topics:
            topic = item.get("topic") if isinstance(item, dict) else None
            count = item.get("count") if isinstance(item, dict) else None
            if topic and isinstance(count, int):
                previous_topic_counts[_normalize_topic(topic)] = count

    topics: List[NewsTopicInsight] = []
    if latest_observation and latest_observation.top_topics:
        window_start = latest_observation.window_start
        window_end = latest_observation.window_end

        topic_sentiments: Dict[str, List[float]] = defaultdict(list)
        related_signals = (
            db.query(NewsSignal)
            .filter(NewsSignal.published_at >= window_start)
            .filter(NewsSignal.published_at <= window_end)
            .all()
        )
        for signal in related_signals:
            if signal.sentiment is None or not signal.topics:
                continue
            for topic in signal.topics:
                normalized_topic = _normalize_topic(topic)
                topic_sentiments[normalized_topic].append(float(signal.sentiment))

        for topic_entry in latest_observation.top_topics:
            topic_name = topic_entry.get("topic") if isinstance(topic_entry, dict) else None
            count = topic_entry.get("count") if isinstance(topic_entry, dict) else None
            if not topic_name or count is None:
                continue
            normalized = _normalize_topic(topic_name)
            previous_count = previous_topic_counts.get(normalized)
            delta = count - (previous_count or 0)
            change_label = f"{delta:+d}건" if previous_count else f"{count}건"

            sentiment_scores = topic_sentiments.get(normalized, [])
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
            sentiment_label = map_sentiment(avg_sentiment)
            topics.append(
                NewsTopicInsight(
                    name=topic_name,
                    change=change_label,
                    sentiment=sentiment_label,
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


@router.get("/sentiment/heatmap", response_model=NewsSentimentHeatmapResponse)
def read_news_sentiment_heatmap(
    window_minutes: int = 60,
    bucket_minutes: int = 15,
    db: Session = Depends(get_db),
) -> NewsSentimentHeatmapResponse:
    return _build_heatmap(db, window_minutes=window_minutes, bucket_minutes=bucket_minutes)


@router.get("/insights", response_model=NewsInsightsResponse)
def read_news_insights(limit: int = 12, db: Session = Depends(get_db)) -> NewsInsightsResponse:
    return _build_news_insights(db, limit=limit)
