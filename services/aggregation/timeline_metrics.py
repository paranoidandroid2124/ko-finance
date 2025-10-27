"\"\"\"Utility helpers for constructing company timeline sparkline payloads.\"\"\""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy.orm import Session

from core.logging import get_logger
from models.news import NewsWindowAggregate

logger = get_logger(__name__)


def _coerce_date(value: Optional[datetime]) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.date()
    if isinstance(value, date):
        return value
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed.date()
    except Exception:  # pragma: no cover - defensive parsing
        return None


def _stride_downsample(points: Sequence[Dict[str, object]], max_points: int) -> List[Dict[str, object]]:
    total = len(points)
    if total <= max_points:
        return list(points)
    step = total / max_points
    downsampled: List[Dict[str, object]] = []
    idx = 0.0
    while len(downsampled) < max_points and int(round(idx)) < total:
        downsampled.append(points[int(round(idx))])
        idx += step
    # ensure last point preserved
    if downsampled[-1] is not points[-1]:
        downsampled.append(points[-1])
    return downsampled


def normalize_timeline_points(raw_points: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    normalized: List[Dict[str, object]] = []
    for raw in raw_points:
        if not isinstance(raw, dict):
            continue
        point_date = _coerce_date(raw.get("date") or raw.get("computed_for"))
        if point_date is None:
            continue
        normalized.append(
            {
                "date": point_date,
                "sentiment_z": raw.get("sentiment_z"),
                "price_close": raw.get("price_close"),
                "volume": raw.get("volume"),
                "event_type": raw.get("event_type"),
            }
        )
    normalized.sort(key=lambda item: item["date"])
    return normalized


def build_timeline_series(
    raw_points: Iterable[Dict[str, object]],
    *,
    max_points: int = 365,
) -> Dict[str, object]:
    normalized = normalize_timeline_points(raw_points)
    downsampled = _stride_downsample(normalized, max_points)
    return {
        "points": downsampled,
        "total_points": len(normalized),
        "downsampled_points": len(downsampled),
    }


def fetch_sentiment_timeline(
    db: Session,
    *,
    ticker: str,
    window_days: int = 365,
) -> List[Dict[str, object]]:
    """Fetches per-day sentiment aggregates for the ticker."""
    if not ticker:
        return []
    window_days = max(1, min(window_days, 365))
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(days=window_days)

    aggregates: Sequence[NewsWindowAggregate] = (
        db.query(NewsWindowAggregate)
        .filter(
            NewsWindowAggregate.ticker == ticker,
            NewsWindowAggregate.window_days == 1,
            NewsWindowAggregate.computed_for >= window_start,
            NewsWindowAggregate.computed_for <= window_end,
        )
        .order_by(NewsWindowAggregate.computed_for.asc())
        .all()
    )

    points: List[Dict[str, object]] = []
    for aggregate in aggregates:
        point_date = _coerce_date(aggregate.computed_for)
        if point_date is None:
            continue
        points.append(
            {
                "date": point_date,
                "sentiment_z": aggregate.sentiment_z,
                "price_close": None,
                "volume": None,
                "event_type": None,
            }
        )

    logger.info(
        "Fetched %d sentiment timeline points for %s (window=%d).",
        len(points),
        ticker,
        window_days,
    )
    return points
