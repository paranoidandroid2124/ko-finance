"\"\"\"Ingestion and aggregation helpers for event study pipelines.\"\"\""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import and_, asc
from sqlalchemy.orm import Session

from core.env import env_str
from models.event_study import EventRecord, EventStudyResult, EventSummary, Price
from models.security_metadata import SecurityMetadata
from models.filing import Filing
from services.event_extractor import EventAttributes, extract_event_attributes

logger = logging.getLogger(__name__)

DEFAULT_BENCHMARK_SYMBOL = env_str("EVENT_STUDY_BENCHMARK", "KOSPI")

_EVENT_TYPES: Tuple[str, ...] = (
    "BUYBACK",
    "BUYBACK_DISPOSAL",
    "SEO",
    "DIVIDEND",
    "RESTATEMENT",
    "CONVERTIBLE",
    "MNA",
    "CONTRACT",
)
_CAP_BUCKETS: Tuple[str, ...] = ("ALL", "LARGE", "MID", "SMALL")


def ingest_events_from_filings(
    db: Session,
    *,
    start_date: date,
    end_date: date,
) -> int:
    """Convert filings in the date range into normalized event records."""

    created = 0
    filings = (
        db.query(Filing)
        .filter(
            Filing.filed_at >= datetime.combine(start_date, datetime.min.time()),
            Filing.filed_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
        )
        .all()
    )
    for filing in filings:
        attributes = extract_event_attributes(filing)
        if not attributes.event_type or not filing.receipt_no:
            continue

        metadata = None
        if filing.ticker:
            metadata = db.get(SecurityMetadata, filing.ticker.upper())

        existing = db.get(EventRecord, filing.receipt_no)
        if existing:
            continue

        event = EventRecord(
            rcept_no=filing.receipt_no,
            corp_code=filing.corp_code or "",
            ticker=(filing.ticker or "").upper() or None,
            corp_name=filing.corp_name,
            event_type=attributes.event_type,
            event_date=filing.filed_at.date() if filing.filed_at else None,
            amount=attributes.amount,
            ratio=attributes.ratio,
            shares=None,
            method=attributes.method,
            score=attributes.score,
            market_cap=metadata.market_cap if metadata else None,
            cap_bucket=metadata.cap_bucket if metadata else None,
            created_at=filing.filed_at or datetime.utcnow(),
            source_url=(filing.urls or {}).get("viewer"),
        )
        db.add(event)
        created += 1

    if created:
        db.commit()
    return created


def update_event_study_series(
    db: Session,
    *,
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL,
    estimation_window: Tuple[int, int] = (-120, -10),
    event_window: Tuple[int, int] = (-5, 20),
) -> int:
    """Compute AR/CAR for events that lack time-series entries."""

    results_created = 0
    events = db.query(EventRecord).all()
    for event in events:
        if not event.ticker or not event.event_date:
            continue

        existing = (
            db.query(EventStudyResult)
            .filter(
                EventStudyResult.rcept_no == event.rcept_no,
                EventStudyResult.t >= event_window[0],
                EventStudyResult.t <= event_window[1],
            )
            .count()
        )
        if existing >= (event_window[1] - event_window[0] + 1):
            continue

        try:
            series = _compute_event_returns(
                db,
                event=event,
                benchmark_symbol=benchmark_symbol,
                estimation_window=estimation_window,
                event_window=event_window,
            )
        except ValueError as exc:
            logger.debug("Skipping %s: %s", event.rcept_no, exc)
            continue

        for t_index, (ar_value, car_value) in series.items():
            record = EventStudyResult(
                rcept_no=event.rcept_no,
                t=t_index,
                ar=ar_value,
                car=car_value,
            )
            db.merge(record)
            results_created += 1

    if results_created:
        db.commit()
    return results_created


def aggregate_event_summaries(
    db: Session,
    *,
    as_of: date,
    window: Tuple[int, int] = (-5, 20),
    scope: str = "market",
) -> int:
    """Aggregate AAR/CAAR statistics per event type."""

    start, end = window
    event_types = list(_EVENT_TYPES)

    summaries_created = 0
    for event_type in event_types:
        for cap_bucket in _CAP_BUCKETS:
            events_query = (
                db.query(EventRecord)
                .filter(EventRecord.event_type == event_type, EventRecord.event_date != None)  # noqa: E711
            )
            if cap_bucket != "ALL":
                events_query = events_query.filter(EventRecord.cap_bucket == cap_bucket)
            events = events_query.all()
            if not events:
                continue

            aar_accumulator: Dict[int, List[float]] = defaultdict(list)
            car_samples: List[float] = []

            for event in events:
                series = (
                    db.query(EventStudyResult)
                    .filter(
                        EventStudyResult.rcept_no == event.rcept_no,
                        EventStudyResult.t >= start,
                        EventStudyResult.t <= end,
                    )
                    .order_by(asc(EventStudyResult.t))
                    .all()
                )
                if len(series) < (end - start + 1):
                    continue
                for row in series:
                    if row.ar is not None:
                        aar_accumulator[row.t].append(float(row.ar))
                final_car = next((row.car for row in series if row.t == end), None)
                if final_car is not None:
                    car_samples.append(float(final_car))

            if len(car_samples) < 5:
                continue

            aar_points = []
            caar_points = []
            cumulative = 0.0
            for t in range(start, end + 1):
                values = aar_accumulator.get(t, [])
                aar_value = sum(values) / len(values) if values else 0.0
                cumulative += aar_value
                aar_points.append({"t": t, "aar": round(aar_value, 6)})
                caar_points.append({"t": t, "caar": round(cumulative, 6)})

            stats = _compute_summary_stats(car_samples)
            histogram = _build_histogram(car_samples)

            payload = EventSummary(
                asof=as_of,
                event_type=event_type,
                window=f"[{start},{end}]",
                scope=scope,
                cap_bucket=cap_bucket,
                filters={"capBucket": cap_bucket} if cap_bucket != "ALL" else None,
                n=stats["n"],
                aar=aar_points,
                caar=caar_points,
                hit_rate=stats["hit_rate"],
                mean_caar=stats["mean"],
                ci_lo=stats["ci_lo"],
                ci_hi=stats["ci_hi"],
                p_value=stats["p_value"],
                dist=histogram,
            )
            db.merge(payload)
            summaries_created += 1

    if summaries_created:
        db.commit()
    return summaries_created


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_event_returns(
    db: Session,
    *,
    event: EventRecord,
    benchmark_symbol: str,
    estimation_window: Tuple[int, int],
    event_window: Tuple[int, int],
) -> Dict[int, Tuple[float, float]]:
    """Return AR/CAR keyed by event-day index."""

    event_day = event.event_date
    if event_day is None:
        raise ValueError("event_date missing")

    estimation_start = event_day + timedelta(days=estimation_window[0])
    estimation_end = event_day + timedelta(days=estimation_window[1])
    event_start = event_day + timedelta(days=event_window[0])
    event_end = event_day + timedelta(days=event_window[1])

    asset_returns = _load_returns(db, event.ticker, estimation_start, event_end)
    benchmark_returns = _load_returns(db, benchmark_symbol, estimation_start, event_end)

    params = _fit_market_model(
        asset_returns,
        benchmark_returns,
        estimation_start,
        estimation_end,
    )

    if params is None:
        raise ValueError("insufficient estimation window")

    alpha, beta = params
    ar_car_series: Dict[int, Tuple[float, float]] = {}
    cumulative = 0.0
    current_date = event_start
    while current_date <= event_end:
        asset_ret = asset_returns.get(current_date)
        bench_ret = benchmark_returns.get(current_date)
        if asset_ret is None or bench_ret is None:
            current_date += timedelta(days=1)
            continue
        expected = alpha + beta * bench_ret
        ar_value = asset_ret - expected
        cumulative += ar_value
        t_index = (current_date - event_day).days
        ar_car_series[t_index] = (round(ar_value, 6), round(cumulative, 6))
        current_date += timedelta(days=1)

    return ar_car_series


def _load_returns(
    db: Session,
    symbol: Optional[str],
    start: date,
    end: date,
) -> Dict[date, float]:
    if not symbol:
        return {}
    rows = (
        db.query(Price)
        .filter(
            Price.symbol == symbol,
            Price.date >= start,
            Price.date <= end,
        )
        .order_by(asc(Price.date))
        .all()
    )
    return {row.date: float(row.ret) for row in rows if row.ret is not None}


def _fit_market_model(
    asset: Dict[date, float],
    bench: Dict[date, float],
    start: date,
    end: date,
) -> Optional[Tuple[float, float]]:
    xs: List[float] = []
    ys: List[float] = []
    current = start
    while current <= end:
        a = asset.get(current)
        b = bench.get(current)
        if a is not None and b is not None:
            xs.append(b)
            ys.append(a)
        current += timedelta(days=1)

    if len(xs) < 30:
        return None

    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    beta = numerator / denominator if denominator else 0.0
    alpha = mean_y - beta * mean_x
    return alpha, beta


def _compute_summary_stats(samples: Sequence[float]) -> Dict[str, float]:
    n = len(samples)
    if n == 0:
        return {"n": 0, "hit_rate": 0.0, "mean": 0.0, "ci_lo": 0.0, "ci_hi": 0.0, "p_value": 1.0}

    m = sum(samples) / n
    hit_rate = sum(1 for value in samples if value > 0) / n
    variance = sum((value - m) ** 2 for value in samples) / max(1, n - 1)
    stddev = math.sqrt(variance)
    se = stddev / math.sqrt(n)
    ci = 1.96 * se
    p_value = _approx_p_value(m, se) if se > 0 else 1.0
    return {"n": n, "hit_rate": hit_rate, "mean": m, "ci_lo": m - ci, "ci_hi": m + ci, "p_value": p_value}


def _approx_p_value(mean_value: float, se: float) -> float:
    if se <= 0:
        return 1.0
    z = mean_value / se
    p = 0.5 * math.erfc(abs(z) / math.sqrt(2))
    return max(1e-6, min(1.0, p))


def _build_histogram(samples: Sequence[float], bins: int = 12) -> List[Dict[str, float]]:
    if not samples:
        return []
    lo = min(samples)
    hi = max(samples)
    if lo == hi:
        lo -= 0.01
        hi += 0.01
    bin_width = (hi - lo) / bins
    histogram = []
    for i in range(bins):
        start = lo + bin_width * i
        end = start + bin_width
        count = sum(1 for value in samples if start <= value < end)
        histogram.append(
            {
                "bin": i,
                "range": [round(start, 6), round(end, 6)],
                "count": count,
            }
        )
    return histogram
