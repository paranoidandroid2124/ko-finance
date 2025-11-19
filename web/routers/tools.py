"""Tool-specific endpoints used by the dashboard overlay."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models.chat import ChatSession
from schemas.api.tools import ToolMemoryWriteRequest, ToolMemoryWriteResponse
from services import event_study_service, lightmem_gate, rag_audit
from services.plan_service import PlanContext
from services.web_utils import parse_uuid
from web.deps import require_plan_feature

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


def _build_event_memory_write(
    ticker: str,
    event_type: str,
    window: int,
    transformed: Dict[str, Any],
) -> Dict[str, Any]:
    summary = transformed.get("summary") or {}
    samples = summary.get("samples")
    win_rate = summary.get("win_rate")
    avg_return = summary.get("avg_return")
    highlights: List[str] = []
    if isinstance(samples, int):
        highlights.append(f"표본 {samples}건")
    if isinstance(win_rate, (int, float)):
        highlights.append(f"승률 {win_rate * 100:.1f}%")
    if isinstance(avg_return, (int, float)):
        highlights.append(f"평균 CAR {avg_return * 100:.2f}%")
    topic = f"{ticker} {event_type} 이벤트 스터디 (T{ -window }~+{window })"
    answer = " / ".join(highlights)
    metadata = {
        "ticker": ticker,
        "event_type": event_type,
        "window": {"start": -window, "end": window},
        "template_slot": "event_study.last_request",
    }
    return {
        "toolId": "event_study",
        "topic": topic,
        "question": f"{ticker} {event_type} 이벤트 스터디 결과를 요약해줘",
        "answer": answer,
        "highlights": highlights,
        "metadata": metadata,
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
        transformed["memory_write"] = _build_event_memory_write(normalized_ticker, normalized_type, window, transformed)
        return transformed
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Event study tool failed: ticker=%s type=%s", normalized_ticker, normalized_type)
        raise HTTPException(status_code=422, detail="이벤트 스터디 계산에 실패했습니다.") from exc
    finally:
        db.close()


def _compute_memory_subject_ids(
    session: ChatSession,
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
) -> Tuple[Optional[str], Optional[str]]:
    tenant_candidate = org_id or session.org_id or session.user_id or user_id
    user_candidate = session.user_id or user_id or org_id or tenant_candidate
    tenant_value = str(tenant_candidate) if tenant_candidate else None
    user_value = str(user_candidate) if user_candidate else None
    if tenant_value and not user_value:
        user_value = tenant_value
    if user_value and not tenant_value:
        tenant_value = user_value
    return tenant_value, user_value


@router.post(
    "/memory",
    response_model=ToolMemoryWriteResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Persist LightMem context generated by Commander tools.",
)
def record_tool_memory(
    payload: ToolMemoryWriteRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
    db: Session = Depends(get_db),
) -> ToolMemoryWriteResponse:
    session: Optional[ChatSession] = (
        db.query(ChatSession)
        .filter(ChatSession.id == payload.sessionId)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat_session_not_found")

    user_uuid = parse_uuid(x_user_id)
    org_uuid = parse_uuid(x_org_id)
    user_settings = lightmem_gate.load_user_settings(user_uuid)
    plan_memory_enabled = lightmem_gate.chat_enabled(plan, user_settings)
    if not plan_memory_enabled:
        return ToolMemoryWriteResponse(stored=False, reason="memory_disabled")

    tenant_value, user_value = _compute_memory_subject_ids(session, user_uuid, org_uuid)
    if not tenant_value or not user_value:
        return ToolMemoryWriteResponse(stored=False, reason="missing_subject")

    question = payload.question or payload.topic
    answer_candidates = [payload.answer] if payload.answer else []
    answer_candidates.extend(payload.highlights)
    answer = " / ".join(part for part in answer_candidates if isinstance(part, str) and part.strip())
    if not answer:
        answer = payload.topic

    stored = rag_audit.store_lightmem_summary(
        question=question,
        answer=answer,
        session=session,
        turn_id=payload.turnId,
        session_key=f"chat:{session.id}",
        tenant_id=tenant_value,
        user_id=user_value,
        plan_memory_enabled=plan_memory_enabled,
        rag_mode=payload.metadata.get("ragMode") or f"tool.{payload.toolId}",
        filing_id=payload.metadata.get("filingId"),
    )
    return ToolMemoryWriteResponse(stored=bool(stored))


__all__ = ["router"]
