"\"\"\"Computation utilities for sector-level sentiment and volume metrics.\"\"\""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from models.news import NewsSignal
from models.sector import NewsArticleSector, SectorDailyMetric, SectorWindowMetric
from services.aggregation.sector_classifier import ensure_sector_catalog

KST = ZoneInfo("Asia/Seoul")
EPSILON = 1e-6
MIN_VOLUME_THRESHOLD = 3
TOP_ARTICLE_LOOKBACK_HOURS = 72
ALPHA = 0.5
BETA = 0.3
GAMMA = 0.2


def _to_kst_date(timestamp: datetime) -> date:
    return timestamp.astimezone(KST).date()


def _utc_from_kst(day: date) -> datetime:
    local_dt = datetime.combine(day, time.min, tzinfo=KST)
    return local_dt.astimezone(timezone.utc)


def _weighted_stats(values: List[float], weights: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if not values:
        return None, None
    total_weight = sum(weights) or 0.0
    if total_weight <= 0:
        return None, None
    mean = sum(v * w for v, w in zip(values, weights)) / total_weight
    if len(values) == 1:
        return mean, 0.0
    variance = sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / total_weight
    stddev = math.sqrt(max(variance, 0.0))
    return mean, stddev


def compute_sector_daily_metrics(session: Session, start_day: date, end_day: date) -> List[SectorDailyMetric]:
    """Compute daily sentiment/volume aggregates for sectors between two dates (inclusive)."""
    start_utc = _utc_from_kst(start_day)
    end_utc = _utc_from_kst(end_day + timedelta(days=1))

    ensure_sector_catalog(session)

    query = (
        session.query(
            NewsArticleSector.sector_id,
            NewsArticleSector.weight,
            NewsSignal.sentiment,
            NewsSignal.published_at,
        )
        .join(NewsSignal, NewsSignal.id == NewsArticleSector.article_id)
        .filter(NewsSignal.published_at >= start_utc)
        .filter(NewsSignal.published_at < end_utc)
    )

    buckets: Dict[int, Dict[date, Dict[str, List[float]]]] = defaultdict(lambda: defaultdict(lambda: {"volume": 0, "sentiments": [], "weights": []}))
    for sector_id, weight, sentiment, published_at in query.all():
        local_day = _to_kst_date(published_at)
        if local_day < start_day or local_day > end_day:
            continue
        bucket = buckets[sector_id][local_day]
        bucket["volume"] += 1
        if sentiment is not None:
            bucket["sentiments"].append(float(sentiment))
            bucket["weights"].append(float(weight or 1.0))

    results: List[SectorDailyMetric] = []
    for sector_id, day_map in buckets.items():
        for day, data in day_map.items():
            sent_mean, sent_std = _weighted_stats(data["sentiments"], data["weights"])
            volume = data["volume"]
            metric = (
                session.query(SectorDailyMetric)
                .filter(SectorDailyMetric.sector_id == sector_id, SectorDailyMetric.date == day)
                .one_or_none()
            )
            if metric is None:
                metric = SectorDailyMetric(sector_id=sector_id, date=day)
                session.add(metric)
            metric.sent_mean = sent_mean
            metric.sent_std = sent_std
            metric.volume = volume
            results.append(metric)

    session.flush()
    return results


def _window_slice(items: Sequence[SectorDailyMetric], start_day: date, end_day: date) -> List[SectorDailyMetric]:
    return [item for item in items if start_day <= item.date <= end_day]


def _mean(values: Iterable[float]) -> Optional[float]:
    values = list(values)
    if not values:
        return None
    return sum(values) / len(values)


def _std(values: Iterable[float], mean_value: float) -> float:
    values = list(values)
    if not values:
        return 0.0
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return math.sqrt(max(variance, 0.0))


def _article_score(signal: NewsSignal, weight: float, as_of: datetime, hours: int) -> float:
    sentiment = float(signal.sentiment or 0.0)
    tone_component = abs(sentiment)

    age_hours = max((as_of - signal.published_at).total_seconds() / 3600.0, 0.0)
    recency_component = max(0.0, 1.0 - min(age_hours, hours) / hours)
    source_component = float(weight or 1.0)

    return ALPHA * tone_component + BETA * recency_component + GAMMA * source_component


def compute_top_articles(session: Session, as_of: datetime, hours: int = TOP_ARTICLE_LOOKBACK_HOURS) -> Dict[int, NewsSignal]:
    """Return best-scoring recent article per sector."""
    cutoff = as_of - timedelta(hours=hours)

    query = (
        session.query(
            NewsArticleSector.sector_id,
            NewsArticleSector.weight,
            NewsSignal,
        )
        .join(NewsSignal, NewsSignal.id == NewsArticleSector.article_id)
        .filter(NewsSignal.published_at >= cutoff)
        .filter(NewsSignal.published_at <= as_of)
    )

    best: Dict[int, Tuple[float, NewsSignal]] = {}
    for sector_id, weight, signal in query.all():
        score = _article_score(signal, weight, as_of, hours)
        if sector_id not in best or score > best[sector_id][0]:
            best[sector_id] = (score, signal)

    return {sector_id: signal for sector_id, (_, signal) in best.items()}


def list_top_articles_for_sector(
    session: Session,
    sector_id: int,
    as_of: datetime,
    *,
    hours: int = TOP_ARTICLE_LOOKBACK_HOURS,
    limit: int = 3,
) -> List[Tuple[NewsSignal, float]]:
    """Return top-N scored articles for a given sector."""
    cutoff = as_of - timedelta(hours=hours)
    query = (
        session.query(NewsArticleSector.weight, NewsSignal)
        .join(NewsSignal, NewsSignal.id == NewsArticleSector.article_id)
        .filter(NewsArticleSector.sector_id == sector_id)
        .filter(NewsSignal.published_at >= cutoff)
        .filter(NewsSignal.published_at <= as_of)
    )

    scored: List[Tuple[NewsSignal, float]] = []
    for weight, signal in query.all():
        score = _article_score(signal, weight, as_of, hours)
        scored.append((signal, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


def compute_sector_window_metrics(
    session: Session,
    as_of_day: date,
    window_days: Sequence[int] = (7, 30, 90),
) -> List[SectorWindowMetric]:
    """Compute rolling window statistics and persist them."""
    ensure_sector_catalog(session)
    unique_windows = sorted({int(window) for window in window_days})
    if not unique_windows:
        return []

    history_span = max(90, max(unique_windows) + 7)
    history_start = as_of_day - timedelta(days=history_span - 1)

    daily_rows = (
        session.query(SectorDailyMetric)
        .filter(SectorDailyMetric.date >= history_start)
        .filter(SectorDailyMetric.date <= as_of_day)
        .all()
    )
    daily_by_sector: Dict[int, List[SectorDailyMetric]] = defaultdict(list)
    for row in daily_rows:
        daily_by_sector[row.sector_id].append(row)
    for items in daily_by_sector.values():
        items.sort(key=lambda metric: metric.date)

    as_of_datetime = datetime.combine(as_of_day, time.max, tzinfo=KST).astimezone(timezone.utc)
    top_articles = compute_top_articles(session, as_of_datetime, hours=TOP_ARTICLE_LOOKBACK_HOURS)

    window_records: List[SectorWindowMetric] = []
    for sector_id, metrics in daily_by_sector.items():
        daily_sent_values = [metric.sent_mean for metric in metrics if metric.sent_mean is not None]
        daily_vol_logs = [math.log1p(metric.volume or 0) for metric in metrics if (metric.volume or 0) > 0]

        sent_baseline_mean = _mean(daily_sent_values)
        sent_baseline_std = _std(daily_sent_values, sent_baseline_mean) if sent_baseline_mean is not None else 0.0
        vol_baseline_mean = _mean(daily_vol_logs)
        vol_baseline_std = _std(daily_vol_logs, vol_baseline_mean) if vol_baseline_mean is not None else 0.0

        for window in unique_windows:
            start = as_of_day - timedelta(days=window - 1)
            window_slice = _window_slice(metrics, start, as_of_day)

            volumes = [item.volume or 0 for item in window_slice]
            volume_sum = sum(volumes)
            sentiments = [item.sent_mean for item in window_slice if item.sent_mean is not None]
            weights = [item.volume or 0 for item in window_slice if item.sent_mean is not None]
            sent_mean, _ = _weighted_stats(sentiments, weights)

            if volume_sum < MIN_VOLUME_THRESHOLD:
                sent_z = 0.0
                vol_z = 0.0
            else:
                baseline_mean = sent_baseline_mean or 0.0
                baseline_std = sent_baseline_std or 0.0
                if baseline_std < EPSILON:
                    sent_z = 0.0
                else:
                    sent_value = sent_mean if sent_mean is not None else baseline_mean
                    sent_z = (sent_value - baseline_mean) / baseline_std

                vol_value = math.log1p(volume_sum)
                baseline_vol_mean = vol_baseline_mean or 0.0
                baseline_vol_std = vol_baseline_std or 0.0
                if baseline_vol_std < EPSILON:
                    vol_z = 0.0
                else:
                    vol_z = (vol_value - baseline_vol_mean) / baseline_vol_std

            prev_window_mean = None
            if window == 7:
                prev_end = start - timedelta(days=1)
                prev_start = prev_end - timedelta(days=window - 1)
                prev_slice = _window_slice(metrics, prev_start, prev_end)
                prev_sentiments = [item.sent_mean for item in prev_slice if item.sent_mean is not None]
                prev_weights = [item.volume or 0 for item in prev_slice if item.sent_mean is not None]
                prev_window_mean, _ = _weighted_stats(prev_sentiments, prev_weights)

            delta_sent = None
            if window == 7 and sent_mean is not None and prev_window_mean is not None:
                delta_sent = sent_mean - prev_window_mean

            record = (
                session.query(SectorWindowMetric)
                .filter(
                    SectorWindowMetric.sector_id == sector_id,
                    SectorWindowMetric.window_days == window,
                    SectorWindowMetric.asof_date == as_of_day,
                )
                .one_or_none()
            )
            if record is None:
                record = SectorWindowMetric(
                    sector_id=sector_id,
                    window_days=window,
                    asof_date=as_of_day,
                )
                session.add(record)

            record.sent_mean = sent_mean
            record.vol_sum = volume_sum
            record.sent_z = sent_z
            record.vol_z = vol_z
            record.delta_sent_7d = delta_sent if window == 7 else None
            record.top_article_id = top_articles.get(sector_id).id if sector_id in top_articles else None

            window_records.append(record)

    session.flush()
    return window_records
