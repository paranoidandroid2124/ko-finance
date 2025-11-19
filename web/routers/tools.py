"""Tool-specific endpoints used by the dashboard overlay."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Body, HTTPException

from database import SessionLocal
from services import event_study_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["Tools"])


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        parsed = float(text)
        if parsed != parsed or parsed in (float("inf"), float("-inf")):
            return None
        return parsed
    except Exception:
        return None


def _transform_event_study_response(summary, events_response) -> Dict[str, Any]:
    """Convert service objects into frontend-friendly JSON."""

    chart_points: List[Dict[str, Any]] = []
    for point in summary.caar:
        day = int(point.get("t", 0))
        car_value = _safe_float(point.get("caar"))
        if car_value is None:
            car_value = 0.0
        chart_points.append({"day": day, "car": round(car_value, 6)})

    history_rows: List[Dict[str, Any]] = []
    for event in (events_response.events or [])[:8]:
        event_date = None
        if getattr(event, "event_date", None):
            event_date = event.event_date.isoformat()
        event_return = _safe_float(getattr(event, "caar", None))
        history_rows.append(
            {
                "date": event_date,
                "type": getattr(event, "event_type", None),
                "return": event_return,
                "corp_name": getattr(event, "corp_name", None),
            }
        )

    return {
        "summary": {
            "samples": summary.n,
            "win_rate": round(summary.hit_rate, 6),
            "avg_return": round(summary.mean_caar, 6),
            "confidence_interval": {
                "low": _safe_float(summary.ci_lo),
                "high": _safe_float(summary.ci_hi),
            },
            "p_value": _safe_float(summary.p_value),
        },
        "chart_data": chart_points,
        "history": history_rows,
    }


@router.post("/event-study")
def event_study_tool(
    payload: dict = Body(
        ...,
        example={"ticker": "005930", "event_type": "earnings", "period_days": 5},
    ),
) -> dict:
    normalized_ticker = event_study_service.normalize_single_value(payload.get("ticker"))
    normalized_type = event_study_service.normalize_single_value(payload.get("event_type") or "earnings")
    period_days = payload.get("period_days") or 5

    if not normalized_ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    if not normalized_type:
        raise HTTPException(status_code=400, detail="event_type is required")
    try:
        window = int(period_days)
        if window <= 0 or window > 30:
            raise ValueError
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="period_days must be between 1 and 30")

    db = SessionLocal()
    try:
        summary = event_study_service.compute_event_metrics(
            db,
            event_type=normalized_type,
            window=(-window, window),
            ticker=normalized_ticker,
            min_samples=1,
        )
        if not summary:
            raise HTTPException(status_code=404, detail="충분한 이벤트 데이터가 없습니다.")
        events_response = event_study_service.fetch_event_rows(
            db,
            limit=10,
            offset=0,
            window_end=window,
            event_types=[normalized_type],
            ticker=normalized_ticker,
            markets=None,
            cap_buckets=None,
            start_date=None,
            end_date=None,
            search_query=None,
        )
        transformed = _transform_event_study_response(summary, events_response)
        transformed["ticker"] = normalized_ticker
        transformed["event_type"] = normalized_type
        transformed["window"] = {"start": -window, "end": window}
        return transformed
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Event study tool failed: ticker=%s type=%s", normalized_ticker, normalized_type)
        raise HTTPException(status_code=422, detail="이벤트 스터디 계산에 실패했습니다.") from exc
    finally:
        db.close()


__all__ = ["router"]
