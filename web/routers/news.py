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


def _resolve_bucket_minutes(window_minutes: int, requested_bucket: int | None) -> int:
    if requested_bucket and requested_bucket > 0:
        return max(5, requested_bucket)

    if window_minutes <= 180:  # up to 3 hours
        return 15
    if window_minutes <= 12 * 60:  # up to half a day
        return 30
    if window_minutes <= 24 * 60:
        return 60
    if window_minutes <= 3 * 24 * 60:
        return 180
    return 360


def _format_bucket_label(offset_minutes: int) -> str:
    if offset_minutes <= 0:
        return "현재"
    if offset_minutes >= 1440:
        days = offset_minutes // 1440
        remaining_minutes = offset_minutes % 1440
        hours = remaining_minutes // 60
        if hours:
            return f"-{days}일 {hours}시간"
        return f"-{days}일"
    if offset_minutes % 60 == 0:
        hours = offset_minutes // 60
        return f"-{hours}시간"
    return f"-{offset_minutes}분"


def _build_heatmap(
    db: Session,
    *,
    window_minutes: int = 60,
    bucket_minutes: int | None = None,
    max_sectors: int = 6,
) -> NewsSentimentHeatmapResponse:
    if window_minutes <= 0:
        window_minutes = 60

    bucket_minutes = _resolve_bucket_minutes(window_minutes, bucket_minutes)
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
        label = _format_bucket_label(offset)
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

    normalized_sectors = {sector.strip() for sector in (sectors or []) if sector.strip()}

    news_items: List[NewsListItem] = []
    filtered_signals: List[tuple[NewsSignal, str, str]] = []

    for entry in candidate_news:
        sector = _classify_sector(entry.topics, entry.ticker)
        sentiment_label = map_sentiment(entry.sentiment)

        if normalized_sectors and sector not in normalized_sectors:
            continue
        if negative_only and sentiment_label != "negative":
            continue
        if exclude_neutral and sentiment_label == "neutral":
            continue

        filtered_signals.append((entry, sector, sentiment_label))
        if len(news_items) < limit:
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
                )
            )

    topic_counts: Counter[str] = Counter()
    topic_sentiments: Dict[str, List[float]] = defaultdict(list)
    topic_labels: Dict[str, str] = {}

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

    top_topics = topic_counts.most_common(5)
    topics: List[NewsTopicInsight] = []
    for normalized, count in top_topics:
        scores = topic_sentiments.get(normalized, [])
        avg_score = sum(scores) / len(scores) if scores else 0.0
        topics.append(
            NewsTopicInsight(
                name=topic_labels.get(normalized, normalized),
                change=f"{count}건",
                sentiment=map_sentiment(avg_score),
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
    bucket_minutes: int | None = Query(default=None, ge=5),
    db: Session = Depends(get_db),
) -> NewsSentimentHeatmapResponse:
    return _build_heatmap(db, window_minutes=window_minutes, bucket_minutes=bucket_minutes)


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










