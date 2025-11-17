"\"\"\"Event study endpoints exposing summary stats and per-event series.\"\"\""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from datetime import date
from typing import List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from database import get_db
from models.event_study import EventRecord, EventStudyResult, EventSummary
from models.filing import Filing
from schemas.api.event_study import (
    EventStudyEventDetail,
    EventStudyEventItem,
    EventStudyEventsResponse,
    EventStudyExportRequest,
    EventStudyExportResponse,
    EventStudyPoint,
    EventStudySeriesPoint,
    EventStudySummaryItem,
    EventStudySummaryResponse,
)
from services import event_study_report, report_renderer
from services.audit_log import record_audit_event
from services.evidence_package import make_evidence_bundle
from services.plan_service import PlanContext
from web.deps import require_plan_feature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/event-study", tags=["Event Study"])


def _normalize_str_list(values: Optional[List[str]]) -> List[str]:
    cleaned: List[str] = []
    for value in values or []:
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped:
            cleaned.append(stripped.upper())
    return cleaned


def _window_key(start: int, end: int) -> str:
    return f"[{start},{end}]"


def _to_float(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _convert_points(rows: Optional[Sequence[dict]], metric_key: str) -> List[EventStudyPoint]:
    points: List[EventStudyPoint] = []
    for entry in rows or []:
        t = entry.get("t")
        if t is None:
            continue
        value = entry.get(metric_key)
        if value is None:
            continue
        try:
            points.append(EventStudyPoint(t=int(t), value=float(value)))
        except (TypeError, ValueError):
            continue
    return points


@router.get("/summary", response_model=EventStudySummaryResponse)
def get_event_study_summary(
    *,
    start: int = Query(-5, description="Event window start (relative days)."),
    end: int = Query(20, description="Event window end (relative days)."),
    scope: str = Query("market", description="Aggregation scope key."),
    significance: float = Query(0.1, alias="sig", description="Maximum p-value to include."),
    event_types: Optional[List[str]] = Query(default=None, alias="eventTypes"),
    cap_buckets: Optional[List[str]] = Query(default=None, alias="capBuckets"),
    db: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature("timeline.full")),
) -> EventStudySummaryResponse:
    if start >= end:
        raise HTTPException(status_code=400, detail="start must be less than end")

    window = _window_key(start, end)
    normalized_types = _normalize_str_list(event_types)
    normalized_caps = _normalize_str_list(cap_buckets)
    target_caps = normalized_caps or ["ALL"]

    latest_subquery = (
        db.query(
            EventSummary.event_type.label("event_type"),
            EventSummary.cap_bucket.label("cap_bucket"),
            func.max(EventSummary.asof).label("max_asof"),
        )
        .filter(EventSummary.window == window, EventSummary.scope == scope, EventSummary.cap_bucket.in_(target_caps))
    )
    if normalized_types:
        latest_subquery = latest_subquery.filter(EventSummary.event_type.in_(normalized_types))
    latest_subquery = latest_subquery.group_by(EventSummary.event_type, EventSummary.cap_bucket).subquery()

    query = (
        db.query(EventSummary)
        .join(
            latest_subquery,
            and_(
                EventSummary.event_type == latest_subquery.c.event_type,
                EventSummary.cap_bucket == latest_subquery.c.cap_bucket,
                EventSummary.asof == latest_subquery.c.max_asof,
            ),
        )
        .filter(EventSummary.window == window, EventSummary.scope == scope, EventSummary.cap_bucket.in_(target_caps))
        .order_by(EventSummary.event_type.asc())
    )
    if normalized_types:
        query = query.filter(EventSummary.event_type.in_(normalized_types))

    rows: Sequence[EventSummary] = query.all()

    items: List[EventStudySummaryItem] = []
    for row in rows:
        if significance is not None and row.p_value is not None and float(row.p_value) > significance:
            continue
        items.append(
            EventStudySummaryItem(
                event_type=row.event_type,
                scope=row.scope,
                cap_bucket=row.cap_bucket,
                window=row.window,
                as_of=row.asof,
                n=row.n,
                hit_rate=_to_float(row.hit_rate) or 0.0,
                mean_caar=_to_float(row.mean_caar) or 0.0,
                ci_lo=_to_float(row.ci_lo) or 0.0,
                ci_hi=_to_float(row.ci_hi) or 0.0,
                p_value=_to_float(row.p_value) or 1.0,
                aar=_convert_points(row.aar, "aar"),
                caar=_convert_points(row.caar, "caar"),
                dist=row.dist or [],
            )
        )

    return EventStudySummaryResponse(
        start=start,
        end=end,
        scope=scope,
        significance=significance,
        results=items,
    )


@router.get("/events", response_model=EventStudyEventsResponse)
def list_event_study_events(
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    window_end: int = Query(10, alias="windowEnd"),
    start_date: Optional[date] = Query(default=None, alias="startDate"),
    end_date: Optional[date] = Query(default=None, alias="endDate"),
    event_types: Optional[List[str]] = Query(default=None, alias="eventTypes"),
    markets: Optional[List[str]] = Query(default=None, alias="markets"),
    cap_buckets: Optional[List[str]] = Query(default=None, alias="capBuckets"),
    search: Optional[str] = Query(default=None, description="Keyword applied to corp name/ticker."),
    db: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature("timeline.full")),
) -> EventStudyEventsResponse:
    normalized_types = _normalize_str_list(event_types)
    normalized_markets = _normalize_str_list(markets)
    normalized_cap_buckets = _normalize_str_list(cap_buckets)
    search_query = search.strip() if isinstance(search, str) and search.strip() else None

    base_query = (
        db.query(EventRecord, Filing.market)
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
    if normalized_cap_buckets:
        base_query = base_query.filter(EventRecord.cap_bucket.in_(normalized_cap_buckets))
    if search_query:
        like_term = f"%{search_query}%"
        base_query = base_query.filter(
            or_(
                EventRecord.corp_name.ilike(like_term),
                EventRecord.ticker.ilike(like_term),
            )
        )

    total = base_query.count()
    rows = (
        base_query.order_by(EventRecord.event_date.desc(), EventRecord.rcept_no.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    receipt_nos = [row.EventRecord.rcept_no for row in rows]
    caar_map: dict[str, Optional[float]] = {}
    peak_map: dict[str, Optional[int]] = {}
    if receipt_nos:
        all_series = (
            db.query(EventStudyResult)
            .filter(EventStudyResult.rcept_no.in_(receipt_nos))
            .all()
        )
        for series_row in all_series:
            key = series_row.rcept_no
            if series_row.t == window_end:
                caar_map[key] = _to_float(series_row.car)
            if series_row.ar is None:
                continue
            current_abs = abs(float(series_row.ar))
            existing = peak_map.get(key)
            if existing is None or current_abs > existing[0]:
                peak_map[key] = (current_abs, series_row.t)

    events: List[EventStudyEventItem] = []
    for record, market in rows:
        events.append(
            EventStudyEventItem(
                receipt_no=record.rcept_no,
                corp_code=record.corp_code,
                corp_name=record.corp_name,
                ticker=record.ticker,
                event_type=record.event_type,
                market=market,
                event_date=record.event_date,
                amount=_to_float(record.amount),
                ratio=_to_float(record.ratio),
                method=record.method,
                score=_to_float(record.score),
                caar=caar_map.get(record.rcept_no),
                aar_peak_day=peak_map.get(record.rcept_no, (None, None))[1] if record.rcept_no in peak_map else None,
                viewer_url=record.source_url,
                cap_bucket=(record.cap_bucket or None),
                market_cap=_to_float(record.market_cap),
            )
        )

    return EventStudyEventsResponse(
        total=total,
        limit=limit,
        offset=offset,
        window_end=window_end,
        events=events,
    )


@router.get("/events/{receipt_no}", response_model=EventStudyEventDetail)
def get_event_detail(
    receipt_no: str,
    *,
    start: int = Query(-5),
    end: int = Query(20),
    db: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature("timeline.full")),
) -> EventStudyEventDetail:
    if start >= end:
        raise HTTPException(status_code=400, detail="start must be less than end")

    event = db.get(EventRecord, receipt_no)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    filing = db.query(Filing).filter(Filing.receipt_no == receipt_no).first()

    series_rows = (
        db.query(EventStudyResult)
        .filter(
            EventStudyResult.rcept_no == receipt_no,
            EventStudyResult.t >= start,
            EventStudyResult.t <= end,
        )
        .order_by(EventStudyResult.t.asc())
        .all()
    )
    series = [
        EventStudySeriesPoint(
            t=row.t,
            ar=_to_float(row.ar),
            car=_to_float(row.car),
        )
        for row in series_rows
    ]

    viewer_url = event.source_url
    if not viewer_url and filing and filing.urls:
        viewer_url = filing.urls.get("viewer")

    return EventStudyEventDetail(
        receipt_no=event.rcept_no,
        corp_code=event.corp_code,
        corp_name=event.corp_name,
        ticker=event.ticker,
        event_type=event.event_type,
        event_date=event.event_date,
        market=filing.market if filing else None,
        scope="market",
        window=_window_key(start, end),
        viewer_url=viewer_url,
        cap_bucket=event.cap_bucket,
    market_cap=_to_float(event.market_cap),
        series=series,
    )


def _optional_path(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    return str(path)


@router.post("/export", response_model=EventStudyExportResponse)
def export_event_study_report_endpoint(
    request: EventStudyExportRequest,
    *,
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(require_plan_feature("reports.event_export")),
    _: PlanContext = Depends(require_plan_feature("timeline.full")),
) -> EventStudyExportResponse:
    if request.window_start >= request.window_end:
        raise HTTPException(status_code=400, detail="windowStart must be less than windowEnd")

    payload = event_study_report.build_event_study_report_payload(
        db,
        window_start=request.window_start,
        window_end=request.window_end,
        scope=request.scope,
        significance=request.significance,
        event_types=request.event_types,
        markets=request.markets,
        cap_buckets=request.cap_buckets,
        start_date=request.start_date,
        end_date=request.end_date,
        search=request.search,
        limit=request.limit,
        requested_by=request.requested_by or plan.tier,
    )

    task_uuid = uuid.uuid4()
    task_id = f"event-study::{task_uuid}"
    pdf_temp_path = report_renderer.render_event_study_report(payload)

    try:
        bundle = make_evidence_bundle(
            task_id=task_id,
            pdf_path=pdf_temp_path,
            brief_payload=payload,
            pdf_filename="event_study_report.pdf",
            payload_filename="event_study_report.json",
        )
    finally:
        try:
            pdf_temp_path.unlink(missing_ok=True)  # type: ignore[arg-type]
        except OSError:
            logger.debug("Failed to remove temporary PDF %s", pdf_temp_path)

    try:
        record_audit_event(
            action="event_study.export",
            source="event_study",
            target_id=task_id,
            extra={
                "plan_tier": plan.tier,
                "filters": request.model_dump(mode="json"),
            },
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("Event study export audit logging skipped: %s", exc, exc_info=True)

    return EventStudyExportResponse(
        task_id=task_id,
        pdf_path=str(bundle.pdf_path),
        pdf_object=bundle.pdf_object,
        pdf_url=bundle.pdf_url,
        package_path=_optional_path(bundle.zip_path),
        package_object=bundle.zip_object,
        package_url=bundle.zip_url,
        manifest_path=_optional_path(bundle.manifest_path),
    )
