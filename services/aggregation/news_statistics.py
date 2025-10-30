"""Shared helpers for aggregating news signal statistics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from models.news import NewsSignal


@dataclass
class NewsSignalSummary:
    article_count: int
    positive_count: int
    neutral_count: int
    negative_count: int
    avg_sentiment: Optional[float]
    min_sentiment: Optional[float]
    max_sentiment: Optional[float]
    topic_counts: Counter[str]


def summarize_news_signals(
    signals: Iterable[NewsSignal],
    *,
    neutral_threshold: float,
) -> NewsSignalSummary:
    """Compute sentiment counts and topic frequencies for a batch of news signals."""
    article_count = 0
    positive_count = 0
    neutral_count = 0
    negative_count = 0
    sentiments: List[float] = []
    topic_counts: Counter[str] = Counter()

    for signal in signals:
        article_count += 1
        sentiment = getattr(signal, "sentiment", None)
        if sentiment is None:
            neutral_count += 1
        else:
            sentiments.append(sentiment)
            if sentiment > neutral_threshold:
                positive_count += 1
            elif sentiment < -neutral_threshold:
                negative_count += 1
            else:
                neutral_count += 1

        for topic in getattr(signal, "topics", None) or []:
            normalized = topic.strip()
            if normalized:
                topic_counts[normalized] += 1

    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None
    min_sentiment = min(sentiments) if sentiments else None
    max_sentiment = max(sentiments) if sentiments else None

    return NewsSignalSummary(
        article_count=article_count,
        positive_count=positive_count,
        neutral_count=neutral_count,
        negative_count=negative_count,
        avg_sentiment=avg_sentiment,
        min_sentiment=min_sentiment,
        max_sentiment=max_sentiment,
        topic_counts=topic_counts,
    )


def build_top_topics(
    topic_counts: Counter[str],
    limit: int,
    *,
    include_weights: bool = False,
) -> List[Dict[str, float]]:
    """Return the top topics with optional weight information."""
    if limit <= 0 or not topic_counts:
        return []

    total = sum(topic_counts.values()) if include_weights else None
    topics = []
    for topic, count in topic_counts.most_common(limit):
        entry: Dict[str, float] = {"topic": topic, "count": count}
        if include_weights and total:
            entry["weight"] = count / total if total else 0.0
        topics.append(entry)
    return topics
