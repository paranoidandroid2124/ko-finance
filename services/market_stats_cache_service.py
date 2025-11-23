"""Market stats cache builder for percentile-based insights."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models.filing import Filing
from models.market_stats_cache import MarketStatsCache
from models.security_metadata import SecurityMetadata

RESTATEMENT_METRIC = "restatement_freq"
DEFAULT_LOOKBACK_DAYS = 365
DEFAULT_PERCENTILES: Sequence[float] = (5, 10, 25, 50, 75, 90, 95)


def _compute_percentile_threshold(sorted_values: Sequence[float], percentile: float) -> Optional[float]:
    """Return the value at the given percentile for a sorted ascending list."""
    if not sorted_values:
        return None
    if percentile <= 0:
        return sorted_values[0]
    if percentile >= 100:
        return sorted_values[-1]
    rank = math.ceil((percentile / 100) * len(sorted_values))
    index = max(0, min(len(sorted_values) - 1, rank - 1))
    return float(sorted_values[index])


def _compute_thresholds(values: Sequence[float], percentiles: Sequence[float]) -> List[Tuple[float, Optional[float]]]:
    sorted_values = sorted(v for v in values if v is not None)
    return [(p, _compute_percentile_threshold(sorted_values, p)) for p in percentiles]


def _load_metadata_map(db: Session, corp_codes: Iterable[str]) -> Dict[str, Dict[str, Optional[str]]]:
    rows = (
        db.query(SecurityMetadata.corp_code, SecurityMetadata.cap_bucket, SecurityMetadata.extra)
        .filter(SecurityMetadata.corp_code.in_(list(corp_codes)))
        .all()
    )
    meta: Dict[str, Dict[str, Optional[str]]] = {}
    for row in rows:
        if not row.corp_code:
            continue
        extra = row.extra or {}
        sector = None
        if isinstance(extra, Mapping):
            sector = extra.get("sector") or extra.get("sector_name") or extra.get("sectorSlug") or extra.get("sector_slug")
        meta[row.corp_code] = {
            "cap_bucket": row.cap_bucket or "unknown",
            "sector": sector or None,
        }
    return meta


def _collect_restatement_counts(
    db: Session,
    *,
    window_start: datetime,
) -> Dict[str, int]:
    rows = (
        db.query(Filing.corp_code, func.count(Filing.id).label("cnt"))
        .filter(
            Filing.filed_at.isnot(None),
            Filing.filed_at >= window_start,
            Filing.receipt_no.isnot(None),
            Filing.corp_code.isnot(None),
            or_(
                Filing.category.in_(("correction", "revision", "정정 공시")),
                func.lower(Filing.title).like("%정정%"),
                func.lower(Filing.report_name).like("%정정%"),
            ),
        )
        .group_by(Filing.corp_code)
        .all()
    )
    return {row.corp_code: int(row.cnt or 0) for row in rows if row.corp_code}


def refresh_restatement_stats(
    db: Session,
    *,
    window_days: int = DEFAULT_LOOKBACK_DAYS,
    percentiles: Sequence[float] = DEFAULT_PERCENTILES,
) -> int:
    """Compute restatement frequency thresholds by cap_bucket and global."""
    window_start = datetime.now(timezone.utc) - timedelta(days=window_days)

    counts = _collect_restatement_counts(db, window_start=window_start)
    if not counts:
        return 0

    meta_map = _load_metadata_map(db, counts.keys())

    buckets_by_segment: Dict[str, Dict[str, List[int]]] = {
        "cap_bucket": {},
        "sector": {},
    }

    for corp_code, count in counts.items():
        meta = meta_map.get(corp_code, {})
        cap_bucket = meta.get("cap_bucket") or "unknown"
        sector = meta.get("sector") or None
        buckets_by_segment["cap_bucket"].setdefault(cap_bucket, []).append(count)
        if sector:
            buckets_by_segment["sector"].setdefault(sector, []).append(count)

    # Always include global bucket
    buckets_by_segment["cap_bucket"]["all"] = list(counts.values())
    if buckets_by_segment["sector"]:
        buckets_by_segment["sector"]["all"] = list(counts.values())

    # Clear old cache for this metric
    db.query(MarketStatsCache).filter(MarketStatsCache.metric == RESTATEMENT_METRIC).delete(synchronize_session=False)

    rows: List[MarketStatsCache] = []
    now = datetime.now(timezone.utc)
    for segment, buckets in buckets_by_segment.items():
        for segment_value, values in buckets.items():
            thresholds = _compute_thresholds(values, percentiles)
            for percentile, value in thresholds:
                rows.append(
                    MarketStatsCache(
                        segment=segment,
                        segment_value=segment_value,
                        metric=RESTATEMENT_METRIC,
                        percentile=percentile,
                        value=value,
                        computed_at=now,
                    )
                )

    db.bulk_save_objects(rows)
    db.commit()
    return len(rows)
