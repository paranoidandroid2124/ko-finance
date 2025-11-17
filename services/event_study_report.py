"""Builder utilities that prepare event study payloads for PDF exports."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from models.event_study import EventRecord, EventStudyResult, EventSummary
from models.filing import Filing


def _normalize_str_list(values: Optional[Iterable[str]]) -> List[str]:
    cleaned: List[str] = []
    seen: set[str] = set()
    for value in values or []:
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if upper in seen:
            continue
        cleaned.append(upper)
        seen.add(upper)
    return cleaned


def _window_key(start: int, end: int) -> str:
    return f"[{start},{end}]"


def _to_float(value: Optional[object]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_percent(value: Optional[float], *, signed: bool = False, digits: int = 2) -> str:
    if value is None:
        return "—"
    pct = value * 100
    sign = "+" if signed and pct > 0 else ""
    formatted = f"{pct:.{digits}f}%"
    return f"{sign}{formatted}"


def _format_number(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}"


def _format_amount(value: Optional[float]) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1_000_000_000:
        return f"{value/1_000_000_000:,.1f}억"
    return f"{value:,.0f}"


def _convert_points(rows: Optional[Sequence[Mapping[str, Any]]], metric_key: str) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for entry in rows or []:
        t = entry.get("t")
        value = entry.get(metric_key)
        try:
            if t is None or value is None:
                continue
            points.append({"t": int(t), "value": float(value)})
        except (TypeError, ValueError):
            continue
    return points


def _series_summary(points: Sequence[Dict[str, Any]], window_end: int) -> Optional[float]:
    for point in points:
        if point.get("t") == window_end:
            return point.get("value")
    return None


def _highlight_from_event(event: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    if not event:
        return None
    return {
        "text": f"{event.get('corpName') or '-'} ({event.get('ticker') or '-'}) • {event.get('eventType') or '-'} • {event.get('caarLabel') or '—'}",
        "viewerUrl": event.get("viewerUrl"),
    }


def build_event_study_report_payload(
    db: Session,
    *,
    window_start: int,
    window_end: int,
    scope: str = "market",
    significance: float = 0.1,
    event_types: Optional[Sequence[str]] = None,
    markets: Optional[Sequence[str]] = None,
    cap_buckets: Optional[Sequence[str]] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = None,
    limit: int = 50,
    requested_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate event study summaries and representative events for PDF rendering."""

    normalized_types = _normalize_str_list(event_types)
    normalized_markets = _normalize_str_list(markets)
    normalized_caps = _normalize_str_list(cap_buckets)
    target_caps = normalized_caps or ["ALL"]
    window_label = _window_key(window_start, window_end)
    limit = max(1, min(int(limit), 200))
    search_query = search.strip() if isinstance(search, str) and search.strip() else None

    # Summary rows (same logic as API)
    latest_subquery = (
        db.query(
            EventSummary.event_type.label("event_type"),
            EventSummary.cap_bucket.label("cap_bucket"),
            func.max(EventSummary.asof).label("max_asof"),
        )
        .filter(EventSummary.window == window_label, EventSummary.scope == scope, EventSummary.cap_bucket.in_(target_caps))
    )
    if normalized_types:
        latest_subquery = latest_subquery.filter(EventSummary.event_type.in_(normalized_types))
    latest_subquery = latest_subquery.group_by(EventSummary.event_type, EventSummary.cap_bucket).subquery()

    summary_query = (
        db.query(EventSummary)
        .join(
            latest_subquery,
            and_(
                EventSummary.event_type == latest_subquery.c.event_type,
                EventSummary.cap_bucket == latest_subquery.c.cap_bucket,
                EventSummary.asof == latest_subquery.c.max_asof,
            ),
        )
        .filter(EventSummary.window == window_label, EventSummary.scope == scope, EventSummary.cap_bucket.in_(target_caps))
        .order_by(EventSummary.event_type.asc())
    )
    if normalized_types:
        summary_query = summary_query.filter(EventSummary.event_type.in_(normalized_types))

    summary_rows: Sequence[EventSummary] = summary_query.all()

    summary_items: List[Dict[str, Any]] = []
    for row in summary_rows:
        if significance is not None and row.p_value is not None and float(row.p_value) > significance:
            continue
        mean_caar = _to_float(row.mean_caar) or 0.0
        hit_rate = _to_float(row.hit_rate) or 0.0
        p_value = _to_float(row.p_value) or 1.0
        caar_series = _convert_points(row.caar, "caar")
        summary_items.append(
            {
                "eventType": row.event_type,
                "eventTypeLabel": row.event_type,
                "sampleSize": row.n,
                "capBucket": row.cap_bucket,
                "meanCaar": mean_caar,
                "meanCaarLabel": _format_percent(mean_caar, signed=True),
                "hitRate": hit_rate,
                "hitRateLabel": _format_percent(hit_rate, digits=1),
                "pValue": p_value,
                "pValueLabel": f"{p_value:.4f}",
                "caarSeries": caar_series,
            }
        )

    total_sample = sum(item["sampleSize"] for item in summary_items) or 0
    if total_sample > 0:
        weighted_mean_caar = sum(item["meanCaar"] * item["sampleSize"] for item in summary_items) / total_sample
        weighted_hit_rate = sum(item["hitRate"] * item["sampleSize"] for item in summary_items) / total_sample
    else:
        weighted_mean_caar = 0.0
        weighted_hit_rate = 0.0

    weighted_p_value: Optional[float] = None
    weighted_rows = [item for item in summary_items if item["pValue"] is not None]
    if weighted_rows:
        total_weight = sum(item["sampleSize"] for item in weighted_rows)
        if total_weight > 0:
            weighted_p_value = sum(item["pValue"] * item["sampleSize"] for item in weighted_rows) / total_weight

    series_block = []
    for item in summary_items:
        final_value = _series_summary(item["caarSeries"], window_end)
        series_block.append(
            {
                "eventType": item["eventTypeLabel"],
                "windowEndValue": _format_percent(final_value, signed=True) if final_value is not None else "—",
                "points": item["caarSeries"],
            }
        )

    # Event listing (subset)
    base_query = (
        db.query(EventRecord, Filing)
        .outerjoin(Filing, Filing.receipt_no == EventRecord.rcept_no)
    )
    if normalized_types:
        base_query = base_query.filter(EventRecord.event_type.in_(normalized_types))
    if start_date:
        base_query = base_query.filter(EventRecord.event_date >= start_date)
    if end_date:
        base_query = base_query.filter(EventRecord.event_date <= end_date)
    if normalized_markets:
        base_query = base_query.filter(Filing.market.in_(normalized_markets))
    if normalized_caps:
        base_query = base_query.filter(EventRecord.cap_bucket.in_(normalized_caps))
    if search_query:
        like_term = f"%{search_query}%"
        base_query = base_query.filter(
            or_(
                EventRecord.corp_name.ilike(like_term),
                EventRecord.ticker.ilike(like_term),
            )
        )

    total_events = base_query.count()
    rows = (
        base_query.order_by(EventRecord.event_date.desc(), EventRecord.rcept_no.desc())
        .limit(limit)
        .all()
    )

    receipt_nos = [record.EventRecord.rcept_no for record in rows]
    caar_map: Dict[str, Optional[float]] = {}
    if receipt_nos:
        series_rows = (
            db.query(EventStudyResult)
            .filter(EventStudyResult.rcept_no.in_(receipt_nos))
            .all()
        )
        for entry in series_rows:
            if entry.t == window_end:
                caar_map[entry.rcept_no] = _to_float(entry.car)

    events_data: List[Dict[str, Any]] = []
    for record, filing in rows:
        viewer_url = record.source_url
        filing_market = None
        if not viewer_url and filing and isinstance(filing.urls, Mapping):
            viewer_url = filing.urls.get("viewer")
        if filing:
            filing_market = filing.market
        caar_value = caar_map.get(record.rcept_no)
        events_data.append(
            {
                "receiptNo": record.rcept_no,
                "corpName": record.corp_name,
                "ticker": record.ticker,
                "eventType": record.event_type,
                "eventDate": record.event_date.isoformat() if record.event_date else None,
                "eventDateLabel": record.event_date.isoformat() if record.event_date else "—",
                "market": filing_market,
                "marketLabel": filing_market or "—",
                "amountLabel": _format_amount(_to_float(record.amount)),
                "capBucket": record.cap_bucket or "—",
                "caar": caar_value,
                "caarLabel": _format_percent(caar_value, signed=True),
                "viewerUrl": viewer_url,
                "marketCapLabel": _format_number(_to_float(record.market_cap)),
            }
        )

    positive_event = max(
        (event for event in events_data if event.get("caar") is not None),
        key=lambda entry: entry["caar"],
        default=None,
    )
    negative_event = min(
        (event for event in events_data if event.get("caar") is not None),
        key=lambda entry: entry["caar"],
        default=None,
    )

    if start_date and end_date:
        date_range_label = f"{start_date.isoformat()} ~ {end_date.isoformat()}"
    elif start_date:
        date_range_label = f"{start_date.isoformat()} 이후"
    elif end_date:
        date_range_label = f"{end_date.isoformat()} 이전"
    else:
        date_range_label = "최근 데이터"

    filter_label = {
        "windowLabel": window_label,
        "eventTypesLabel": ", ".join(normalized_types) if normalized_types else "전체",
        "marketsLabel": ", ".join(normalized_markets) if normalized_markets else "전체",
        "capBucketsLabel": ", ".join(target_caps) if target_caps else "ALL",
        "dateRangeLabel": date_range_label,
        "searchLabel": search_query or "—",
    }

    metrics_block = {
        "sampleSize": total_sample,
        "weightedMeanCaar": _format_percent(weighted_mean_caar, signed=True),
        "weightedHitRate": _format_percent(weighted_hit_rate, digits=1),
        "weightedPValue": f"{weighted_p_value:.4f}" if weighted_p_value is not None else "—",
        "windowStart": window_start,
        "windowEnd": window_end,
    }

    return {
        "report": {
            "title": "Event Study Report",
            "subtitle": f"{scope.upper()} Window {window_label}",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "requestedBy": requested_by or "system",
        },
        "filters": filter_label,
        "metrics": metrics_block,
        "summary": summary_items,
        "series": series_block,
        "events": {
            "total": total_events,
            "rows": events_data,
            "limit": limit,
        },
        "highlights": {
            "topPositive": _highlight_from_event(positive_event),
            "topNegative": _highlight_from_event(negative_event),
        },
    }


__all__ = ["build_event_study_report_payload"]
