import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore

from parse.tasks import tally_news_window


def _make_signal(sentiment, topics):
    return SimpleNamespace(sentiment=sentiment, topics=topics)


def test_tally_news_window_counts_and_topics():
    window_start = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    window_end = window_start + timedelta(minutes=60)

    signals = [
        _make_signal(0.7, ["AI", "Macro"]),
        _make_signal(-0.4, ["Macro", "Rates"]),
        _make_signal(0.05, ["AI"]),
        _make_signal(None, ["Macro"]),
    ]

    metrics = tally_news_window(
        signals,
        window_start,
        window_end,
        topics_limit=3,
        neutral_threshold=0.1,
    )

    assert metrics["window_start"] == window_start
    assert metrics["window_end"] == window_end
    assert metrics["article_count"] == 4
    assert metrics["positive_count"] == 1
    assert metrics["negative_count"] == 1
    assert metrics["neutral_count"] == 2
    assert metrics["avg_sentiment"] is not None
    top_topics = metrics["top_topics"]
    assert top_topics[0]["topic"] == "Macro"
    assert top_topics[0]["count"] == 3
    assert any(item["topic"] == "AI" for item in top_topics)


def test_tally_news_window_empty_signals():
    window_start = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    window_end = window_start + timedelta(minutes=60)

    metrics = tally_news_window(
        [],
        window_start,
        window_end,
        topics_limit=5,
        neutral_threshold=0.1,
    )

    assert metrics["article_count"] == 0
    assert metrics["avg_sentiment"] is None
    assert metrics["top_topics"] == []
    assert metrics["positive_count"] == 0
    assert metrics["negative_count"] == 0
    assert metrics["neutral_count"] == 0
