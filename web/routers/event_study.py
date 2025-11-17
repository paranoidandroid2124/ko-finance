"\"\"\"Event study endpoints exposing summary stats and per-event series.\"\"\""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.event_study import (
    EventStudyEventDetail,
    EventStudyEventsResponse,
    EventStudyExportRequest,
    EventStudyExportResponse,
    EventStudyMetricsResponse,
    EventStudySummaryResponse,
    EventStudyWindowListResponse,
)
from services import event_study_report, event_study_service, report_renderer
from services.audit_log import record_audit_event
from services.evidence_package import make_evidence_bundle
from services.plan_service import PlanContext
from web.deps import require_plan_feature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/event-study", tags=["Event Study"])


@router.get("/windows", response_model=EventStudyWindowListResponse)
def list_event_windows(
    *,
    db: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature("timeline.full")),
) -> EventStudyWindowListResponse:
    presets = event_study_service.list_window_presets(db)
    default_key = event_study_service.default_window_key(db)
    return EventStudyWindowListResponse(
        default_key=default_key,
        windows=[
            {
                "key": preset.key,
                "label": preset.label,
                "description": preset.description,
                "start": preset.start,
                "end": preset.end,
            }
            for preset in presets
        ],
    )


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

    normalized_types = event_study_service.normalize_str_list(event_types)
    normalized_caps = event_study_service.normalize_str_list(cap_buckets)

    return event_study_service.summarize_event_window(
        db,
        start=start,
        end=end,
        scope=scope,
        significance=significance,
        event_types=normalized_types or None,
        cap_buckets=normalized_caps or None,
    )


@router.get("/metrics", response_model=EventStudyMetricsResponse)
def get_event_study_metrics(
    *,
    window_key: Optional[str] = Query(default=None, alias="windowKey"),
    event_type: str = Query(..., alias="eventType"),
    ticker: str = Query(...),
    significance: float = Query(0.1, alias="sig", gt=0.0, le=0.5),
    start_date: Optional[date] = Query(default=None, alias="startDate"),
    end_date: Optional[date] = Query(default=None, alias="endDate"),
    cap_buckets: Optional[List[str]] = Query(default=None, alias="capBuckets"),
    markets: Optional[List[str]] = Query(default=None, alias="markets"),
    search: Optional[str] = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature("timeline.full")),
) -> EventStudyMetricsResponse:
    normalized_type = event_study_service.normalize_single_value(event_type)
    normalized_ticker = event_study_service.normalize_single_value(ticker)
    if not normalized_type:
        raise HTTPException(status_code=400, detail="eventType is required")
    if not normalized_ticker:
        raise HTTPException(status_code=400, detail="ticker is required")

    normalized_caps = event_study_service.normalize_str_list(cap_buckets)
    normalized_markets = event_study_service.normalize_str_list(markets)
    search_query = search.strip() if isinstance(search, str) and search.strip() else None

    preset = event_study_service.resolve_window_preset(db, window_key)
    summary = event_study_service.compute_event_metrics(
        db,
        event_type=normalized_type,
        window=(preset.start, preset.end),
        ticker=normalized_ticker,
        markets=normalized_markets or None,
        cap_buckets=normalized_caps or None,
        start_date=start_date,
        end_date=end_date,
        search=search_query,
        significance=significance,
        min_samples=1,
    )
    if not summary:
        raise HTTPException(status_code=404, detail="No events matched the requested filters")

    events_response = event_study_service.fetch_event_rows(
        db,
        limit=limit,
        offset=offset,
        window_end=preset.end,
        event_types=[normalized_type],
        ticker=normalized_ticker,
        markets=normalized_markets or None,
        cap_buckets=normalized_caps or None,
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
    )

    return EventStudyMetricsResponse(
        window_key=preset.key,
        window_label=preset.label,
        start=preset.start,
        end=preset.end,
        event_type=normalized_type,
        ticker=normalized_ticker,
        cap_bucket=normalized_caps[0] if normalized_caps else None,
        scope="market",
        significance=significance,
        n=summary.n,
        hit_rate=summary.hit_rate,
        mean_caar=summary.mean_caar,
        ci_lo=summary.ci_lo,
        ci_hi=summary.ci_hi,
        p_value=summary.p_value,
        aar=event_study_service.convert_points(summary.aar, "aar"),
        caar=event_study_service.convert_points(summary.caar, "caar"),
        dist=summary.dist,
        events=events_response,
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
    normalized_types = event_study_service.normalize_str_list(event_types)
    normalized_markets = event_study_service.normalize_str_list(markets)
    normalized_cap_buckets = event_study_service.normalize_str_list(cap_buckets)
    search_query = search.strip() if isinstance(search, str) and search.strip() else None

    return event_study_service.fetch_event_rows(
        db,
        limit=limit,
        offset=offset,
        window_end=window_end,
        event_types=normalized_types or None,
        ticker=None,
        markets=normalized_markets or None,
        cap_buckets=normalized_cap_buckets or None,
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
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

    detail = event_study_service.load_event_detail(
        db,
        receipt_no=receipt_no,
        start=start,
        end=end,
    )
    if not detail:
        raise HTTPException(status_code=404, detail="Event not found")

    return detail


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
