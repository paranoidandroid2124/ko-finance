"""Compute longer horizon news sentiment metrics (7/30 day windows)."""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.logging import get_logger
from models.news import NewsSignal, NewsWindowAggregate
from services.reliability.source_reliability import (
    apply_window_penalties,
    average_reliability,
    normalize_domain,
    score_article,
)

logger = get_logger(__name__)

DOMESTIC_TLDS = (".kr", ".co.kr", ".go.kr", ".or.kr", ".re.kr", ".pe.kr", ".ne.kr")


def compute_news_window_metrics(
    db: Session,
    window_end: datetime,
    window_days: int,
    scope: str = "global",
    ticker: Optional[str] = None,
) -> NewsWindowAggregate:
    """Compute and persist windowed news metrics for the provided scope."""
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=timezone.utc)
    window_start = window_end - timedelta(days=window_days)

    query = db.query(NewsSignal).filter(
        NewsSignal.published_at >= window_start,
        NewsSignal.published_at < window_end,
    )
    if ticker:
        query = query.filter(NewsSignal.ticker == ticker)
    signals: List[NewsSignal] = query.all()

    article_count = len(signals)
    reliability_scores: List[float] = []
    updated_reliability = False
    for signal in signals:
        current_reliability = getattr(signal, "source_reliability", None)
        if current_reliability is None:
            computed = score_article(getattr(signal, "source", None), getattr(signal, "url", None))
            try:
                setattr(signal, "source_reliability", computed)
                updated_reliability = True
            except (AttributeError, TypeError):
                pass
            current_reliability = computed
        if current_reliability is not None:
            reliability_scores.append(float(current_reliability))
    sentiments = [signal.sentiment for signal in signals if signal.sentiment is not None]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None
    aggregate_reliability = average_reliability(reliability_scores)

    sentiment_z = _compute_sentiment_z_score(db, avg_sentiment)
    topic_counts = _collect_topic_counts(signals)
    top_topics = _calculate_top_topics(topic_counts)
    novelty_kl = _compute_novelty(db, window_start, window_end, window_days, scope, ticker, topic_counts)
    topic_shift = _compute_topic_shift(db, window_start, window_end, window_days, scope, ticker, topic_counts)
    domestic_ratio, domain_diversity = _compute_domain_metrics(signals, article_count)

    record = (
        db.query(NewsWindowAggregate)
        .filter(
            NewsWindowAggregate.scope == scope,
            NewsWindowAggregate.ticker == ticker,
            NewsWindowAggregate.window_days == window_days,
            NewsWindowAggregate.computed_for == window_end,
        )
        .one_or_none()
    )
    if not record:
        record = NewsWindowAggregate(
            scope=scope,
            ticker=ticker,
            window_days=window_days,
            computed_for=window_end,
        )

    record.article_count = article_count
    record.avg_sentiment = avg_sentiment
    record.sentiment_z = sentiment_z
    record.novelty_kl = novelty_kl
    record.topic_shift = topic_shift
    record.domestic_ratio = domestic_ratio
    record.domain_diversity = domain_diversity
    domain_counts: Counter[str] = Counter()
    for signal in signals:
        domain = normalize_domain(getattr(signal, "url", None))
        if domain:
            domain_counts[domain] += 1

    aggregate_reliability = apply_window_penalties(aggregate_reliability, domain_counts)

    record.source_reliability = aggregate_reliability
    record.top_topics = top_topics

    db.add(record)
    if updated_reliability:
        db.flush()
    db.commit()

    logger.info(
        "Computed %s news metrics window=%dd articles=%d sentiment=%.3f z=%.3f reliability=%.3f",
        scope,
        window_days,
        article_count,
        avg_sentiment if avg_sentiment is not None else float("nan"),
        sentiment_z if sentiment_z is not None else float("nan"),
        aggregate_reliability if aggregate_reliability is not None else float("nan"),
    )
    return record


def _compute_sentiment_z_score(db: Session, avg_sentiment: Optional[float]) -> Optional[float]:
    if avg_sentiment is None:
        return None
    mean_std = (
        db.query(func.avg(NewsSignal.sentiment), func.stddev_pop(NewsSignal.sentiment))
        .filter(NewsSignal.sentiment.isnot(None))
        .one()
    )
    global_mean = mean_std[0]
    global_std = mean_std[1]
    if global_mean is None or not global_std or math.isclose(global_std, 0.0, abs_tol=1e-6):
        return None
    return (avg_sentiment - global_mean) / global_std


def _collect_topic_counts(signals: Iterable[NewsSignal]) -> Counter:
    counts: Counter = Counter()
    for signal in signals:
        if not signal.topics:
            continue
        for topic in signal.topics:
            normalized = topic.strip()
            if normalized:
                counts[normalized] += 1
    return counts


def _calculate_top_topics(counts: Counter, limit: int = 10) -> List[Dict[str, float]]:
    total = sum(counts.values())
    if total == 0:
        return []
    top = counts.most_common(limit)
    return [
        {"topic": topic, "count": count, "weight": count / total}
        for topic, count in top
    ]


def _compute_domain_metrics(signals: Iterable[NewsSignal], article_count: int) -> Tuple[Optional[float], Optional[float]]:
    if article_count == 0:
        return (None, None)
    domains = []
    domestic = 0
    for signal in signals:
        domain = normalize_domain(getattr(signal, "url", None))
        if not domain:
            continue
        domains.append(domain)
        if domain.endswith(DOMESTIC_TLDS):
            domestic += 1
    if not domains:
        return (None, None)
    unique_domains = len(set(domains))
    domestic_ratio = domestic / len(domains) if domains else None
    diversity = unique_domains / len(domains)
    return domestic_ratio, diversity


def _compute_novelty(
    db: Session,
    window_start: datetime,
    window_end: datetime,
    window_days: int,
    scope: str,
    ticker: Optional[str],
    current_counts: Counter,
) -> Optional[float]:
    previous_start = window_start - timedelta(days=window_days)
    previous_end = window_start

    query = db.query(NewsSignal).filter(
        NewsSignal.published_at >= previous_start,
        NewsSignal.published_at < previous_end,
    )
    if ticker:
        query = query.filter(NewsSignal.ticker == ticker)
    previous_counts = _collect_topic_counts(query.all())
    if not current_counts or not previous_counts:
        return None

    return _kl_divergence(current_counts, previous_counts)


def _kl_divergence(current: Counter, previous: Counter) -> float:
    total_current = sum(current.values())
    total_previous = sum(previous.values())
    if total_current == 0 or total_previous == 0:
        return 0.0

    epsilon = 1e-6
    divergence = 0.0

    for topic, current_count in current.items():
        p = current_count / total_current
        q = (previous.get(topic, 0) + epsilon) / (total_previous + epsilon * len(current))
        divergence += p * math.log(p / q)
    return divergence


def _compute_topic_shift(
    db: Session,
    window_start: datetime,
    window_end: datetime,
    window_days: int,
    scope: str,
    ticker: Optional[str],
    current_counts: Counter,
) -> Optional[float]:
    previous_start = window_start - timedelta(days=window_days)
    previous_end = window_start

    query = db.query(NewsSignal).filter(
        NewsSignal.published_at >= previous_start,
        NewsSignal.published_at < previous_end,
    )
    if ticker:
        query = query.filter(NewsSignal.ticker == ticker)
    previous_counts = _collect_topic_counts(query.all())
    if not current_counts or not previous_counts:
        return None

    return _cosine_distance(current_counts, previous_counts)


def _cosine_distance(current: Counter, previous: Counter) -> float:
    # Create combined vocabulary
    vocab = set(current.keys()) | set(previous.keys())
    if not vocab:
        return 0.0

    def vectorize(counter: Counter) -> List[float]:
        return [float(counter.get(term, 0.0)) for term in vocab]

    current_vec = vectorize(current)
    previous_vec = vectorize(previous)

    dot = sum(a * b for a, b in zip(current_vec, previous_vec))
    norm_a = math.sqrt(sum(a * a for a in current_vec))
    norm_b = math.sqrt(sum(b * b for b in previous_vec))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    cosine_similarity = dot / (norm_a * norm_b)
    return 1.0 - cosine_similarity
