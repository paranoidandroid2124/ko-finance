"\"\"\"Ingestion and aggregation helpers for event study pipelines.\"\"\""

from __future__ import annotations

import logging
import math
from collections import defaultdict
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import and_, asc
from sqlalchemy.orm import Session

from core.env import env_str
from database import SessionLocal
from models.alert import AlertRule
from models.event_study import (
    EventAlertMatch,
    EventIngestJob,
    EventRecord,
    EventStudyResult,
    EventSummary,
    Price,
)
from models.security_metadata import SecurityMetadata
from models.filing import Filing
from services.event_extractor import EventAttributes, extract_event_attributes, get_event_rule_metadata

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


_DOMAIN_EVENT_WINDOWS: Dict[str, Tuple[int, int]] = {
    "REGULATORY": (-1, 3),
    "LEGAL": (-1, 5),
    "ESG": (0, 3),
    "CYBER": (0, 3),
    "GUIDANCE": (-1, 1),
    "FIN": (0, 3),
    "PRODUCT": (0, 3),
    "SUPPLY": (0, 5),
    "CREDIT": (0, 3),
    "MARKET": (0, 1),
}
_MARKET_CLOSE_HOUR = 16


def ingest_events_from_filings(
    db: Session,
    *,
    start_date: date,
    end_date: date,
) -> int:
    """Convert filings in the date range into normalized event records."""

    job = _create_ingest_job(start_date, end_date)
    created = 0
    skipped = 0

    filings_query = (
        db.query(Filing)
        .filter(
            Filing.filed_at >= datetime.combine(start_date, datetime.min.time()),
            Filing.filed_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
        )
        .order_by(Filing.filed_at.asc())
    )
    try:
        for filing in filings_query.yield_per(500):
            attributes = extract_event_attributes(filing)
            if not attributes.event_type or not filing.receipt_no:
                continue

            metadata = None
            if filing.ticker:
                metadata = db.get(SecurityMetadata, filing.ticker.upper())

            existing = db.get(EventRecord, filing.receipt_no)
            if existing:
                skipped += 1
                continue

            event_day = filing.filed_at.date() if filing.filed_at else None
            if (
                event_day
                and filing.filed_at
                and attributes.timing_rule == "AFTER_CLOSE_DPLUS1"
                and filing.filed_at.hour >= _MARKET_CLOSE_HOUR
            ):
                event_day = event_day + timedelta(days=1)

            metadata_payload: Dict[str, object] = {
                "timingRule": attributes.timing_rule,
                "matches": attributes.matches,
            }
            event = EventRecord(
                rcept_no=filing.receipt_no,
                corp_code=filing.corp_code or "",
                ticker=(filing.ticker or "").upper() or None,
                corp_name=filing.corp_name,
                event_type=attributes.event_type,
                event_date=event_day,
                amount=attributes.amount,
                ratio=attributes.ratio,
                shares=None,
                method=attributes.method,
                score=attributes.score,
                domain=attributes.domain,
                subtype=attributes.subtype,
                confidence=attributes.confidence,
                is_negative=attributes.is_negative,
                is_restatement=attributes.is_restatement,
                matches=attributes.matches or None,
                market_cap=metadata.market_cap if metadata else None,
                cap_bucket=metadata.cap_bucket if metadata else None,
                created_at=filing.filed_at or datetime.utcnow(),
                source_url=(filing.urls or {}).get("viewer"),
                metadata=metadata_payload,
            )
            db.add(event)
            _record_event_alert_matches(db, event, attributes)
            created += 1

        db.commit()
        _update_ingest_job(
            job.id,
            status="completed",
            events_created=created,
            events_skipped=skipped,
        )
    except Exception as exc:  # pragma: no cover - ingestion guard
        logger.exception("Event ingestion failed: %s", exc)
        db.rollback()
        _update_ingest_job(
            job.id,
            status="failed",
            events_created=created,
            events_skipped=skipped,
            errors={"message": str(exc)},
        )
        raise

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

        window = _resolve_event_window(event_window, event.event_type)
        existing = (
            db.query(EventStudyResult)
            .filter(
                EventStudyResult.rcept_no == event.rcept_no,
                EventStudyResult.t >= window[0],
                EventStudyResult.t <= window[1],
            )
            .count()
        )
        if existing >= (window[1] - window[0] + 1):
            continue

        try:
            series = _compute_event_returns(
                db,
                event=event,
                benchmark_symbol=benchmark_symbol,
                estimation_window=estimation_window,
                event_window=window,
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


def _resolve_event_window(default_window: Tuple[int, int], event_type: Optional[str]) -> Tuple[int, int]:
    if not event_type:
        return default_window
    metadata = get_event_rule_metadata(event_type)
    domain = metadata["domain"] if metadata and "domain" in metadata else "FIN"
    return _DOMAIN_EVENT_WINDOWS.get(domain, default_window)


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


def _create_ingest_job(start_date: date, end_date: date) -> EventIngestJob:
    session = SessionLocal()
    try:
        job = EventIngestJob(
            window_start=start_date,
            window_end=end_date,
            status="processing",
            events_created=0,
            events_skipped=0,
            metadata={"source": "filings"},
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job
    finally:
        session.close()


def _update_ingest_job(
    job_id: uuid.UUID,
    *,
    status: Optional[str] = None,
    events_created: Optional[int] = None,
    events_skipped: Optional[int] = None,
    errors: Optional[Dict[str, Any]] = None,
) -> None:
    session = SessionLocal()
    try:
        job = session.get(EventIngestJob, job_id)
        if not job:
            return
        if status:
            job.status = status
        if events_created is not None:
            job.events_created = events_created
        if events_skipped is not None:
            job.events_skipped = events_skipped
        if errors is not None:
            job.errors = errors
        job.updated_at = datetime.now(timezone.utc)
        session.commit()
    finally:
        session.close()


def _record_event_alert_matches(db: Session, event: EventRecord, attributes: EventAttributes) -> None:
    matches = _match_alert_rules_for_event(db, event, attributes)
    if not matches:
        return
    now = datetime.now(timezone.utc)
    for rule, score, metadata in matches:
        existing = (
            db.query(EventAlertMatch)
            .filter(EventAlertMatch.event_id == event.rcept_no, EventAlertMatch.alert_id == rule.id)
            .first()
        )
        if existing:
            existing.match_score = score
            existing.metadata = metadata
            existing.matched_at = now
        else:
            db.add(
                EventAlertMatch(
                    event_id=event.rcept_no,
                    alert_id=rule.id,
                    match_score=score,
                    metadata=metadata,
                    matched_at=now,
                )
            )


def _match_alert_rules_for_event(
    db: Session,
    event: EventRecord,
    attributes: EventAttributes,
) -> List[Tuple[AlertRule, float, Dict[str, Any]]]:
    ticker = (event.ticker or "").upper()
    if not ticker:
        return []
    candidates = (
        db.query(AlertRule)
        .filter(AlertRule.status == "active")
        .all()
    )
    matches: List[Tuple[AlertRule, float, Dict[str, Any]]] = []
    for rule in candidates:
        trigger = rule.trigger or {}
        trigger_type = str(trigger.get("type") or "filing").lower()
        if trigger_type != "filing":
            continue
        tickers = {
            str(value).strip().upper()
            for value in (trigger.get("tickers") or [])
            if isinstance(value, str) and value.strip()
        }
        if not tickers or ticker not in tickers:
            continue
        score = 1.0
        metadata = {
            "ticker": ticker,
            "eventType": event.event_type,
            "ruleName": rule.name,
            "matchSource": "event_ingest",
            "subtype": attributes.subtype,
        }
        matches.append((rule, score, metadata))
    return matches
