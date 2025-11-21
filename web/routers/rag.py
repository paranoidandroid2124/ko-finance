"""FastAPI routes for the Interactive Analyst (RAG) module."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from database import get_db, SessionLocal
from schemas.api.rag import (
    RAGDeeplinkPayload,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGTelemetryRequest,
    RAGTelemetryResponse,
)
from schemas.api.rag_v2 import (
    RagGridJobResponse,
    RagGridRequest,
    RagGridResponse,
    RagQueryRequest as RagQueryV2Request,
    RagQueryResponse as RagQueryV2Response,
)
from services.plan_service import PlanContext
from services.web_utils import parse_uuid
from services import rag_service, rag_audit
from web.deps import require_plan_feature
from web.quota_guard import enforce_quota

try:  # pragma: no cover - optional Celery dependency
    from parse.tasks import run_rag_self_check as _run_rag_self_check_task
    from parse.tasks import snapshot_evidence_diff as _snapshot_evidence_diff_task
except Exception:  # pragma: no cover
    _run_rag_self_check_task = None
    _snapshot_evidence_diff_task = None

run_rag_self_check = _run_rag_self_check_task
snapshot_evidence_diff = _snapshot_evidence_diff_task
attach_diff_metadata = rag_audit.attach_evidence_diff
_enqueue_evidence_snapshot = rag_audit.enqueue_evidence_snapshot
rag_metrics = rag_service.rag_metrics
deeplink_service = rag_service.deeplink_service
NO_CONTEXT_ANSWER = rag_service.NO_CONTEXT_ANSWER

router = APIRouter(prefix="/rag", tags=["RAG"])


def _enforce_rag_chat_quota(plan: PlanContext, x_user_id: Optional[str], x_org_id: Optional[str]) -> None:
    enforce_quota(
        "rag.chat",
        plan=plan,
        user_id=parse_uuid(x_user_id),
        org_id=parse_uuid(x_org_id),
    )


@router.get(
    "/deeplink/{token}",
    response_model=RAGDeeplinkPayload,
    name="rag.deeplink.resolve",
)
def resolve_rag_deeplink(token: str) -> RAGDeeplinkPayload:
    return rag_service.resolve_rag_deeplink(token)


@router.post(
    "/telemetry",
    response_model=RAGTelemetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def record_rag_telemetry(
    telemetry: RAGTelemetryRequest,
    request: Request,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
) -> RAGTelemetryResponse:
    return rag_service.record_rag_telemetry(telemetry, request, x_user_id, x_org_id, plan)


@router.post("/query", response_model=RAGQueryResponse)
def query_rag(
    request: RAGQueryRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    idempotency_key_header: Optional[str] = Header(default=None, convert_underscores=False, alias="Idempotency-Key"),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
    db: Session = Depends(get_db),
) -> RAGQueryResponse:
    _enforce_rag_chat_quota(plan, x_user_id, x_org_id)
    question_text = getattr(request, "question", None)
    if question_text is None:
        question_text = getattr(request, "query", "")
    return rag_service.query_rag(
        request,
        x_user_id,
        x_org_id,
        idempotency_key_header,
        plan,
        db,
        route_decision=None,
    )


@router.post("/query/stream")
def query_rag_stream(
    request: RAGQueryRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    idempotency_key_header: Optional[str] = Header(default=None, convert_underscores=False, alias="Idempotency-Key"),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
) -> StreamingResponse:
    _enforce_rag_chat_quota(plan, x_user_id, x_org_id)
    session = SessionLocal()
    try:
        question_text = getattr(request, "question", None)
        if question_text is None:
            question_text = getattr(request, "query", "")
        response = rag_service.query_rag_stream(
            request,
            x_user_id,
            x_org_id,
            idempotency_key_header,
            plan,
            session,
            route_decision=None,
        )
    except Exception:
        session.close()
        raise
    if response.background is None:
        response.background = BackgroundTask(session.close)
    else:
        original_background = response.background

        def _combined_background() -> None:
            try:
                original_background()
            finally:
                session.close()

        response.background = BackgroundTask(_combined_background)
    return response


@router.post(
    "/query/v2",
    response_model=RagQueryV2Response,
    summary="거래 지향 RAG 질의 (Evidence-first, Beta)",
)
def query_rag_v2(
    payload: RagQueryV2Request,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
    db: Session = Depends(get_db),
) -> RagQueryV2Response:
    _enforce_rag_chat_quota(plan, x_user_id, x_org_id)
    return rag_service.query_rag_v2(
        payload,
        x_user_id,
        x_org_id,
        plan,
        db,
        route_decision=None,
    )


@router.post(
    "/query/grid",
    response_model=RagGridResponse,
    summary="멀티 문서 QA Grid (Beta)",
)
def query_rag_grid(
    payload: RagGridRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
    db: Session = Depends(get_db),
) -> RagGridResponse:
    _enforce_rag_chat_quota(plan, x_user_id, x_org_id)
    return rag_service.query_rag_grid(payload, x_user_id, x_org_id, plan, db)


@router.post(
    "/grid",
    response_model=RagGridJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="QA Grid 비동기 잡 생성",
)
def create_rag_grid_job(
    payload: RagGridRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
    db: Session = Depends(get_db),
) -> RagGridJobResponse:
    _enforce_rag_chat_quota(plan, x_user_id, x_org_id)
    return rag_service.create_rag_grid_job(payload, x_user_id, x_org_id, plan, db)


@router.get(
    "/grid/{job_id}",
    response_model=RagGridJobResponse,
    summary="QA Grid 잡 상태 조회",
)
def read_rag_grid_job(
    job_id: uuid.UUID,
    _user_id: Optional[str] = Header(default=None),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
    db: Session = Depends(get_db),
) -> RagGridJobResponse:
    return rag_service.read_rag_grid_job(job_id, _user_id, plan, db)


__all__ = [
    "router",
    "run_rag_self_check",
    "snapshot_evidence_diff",
    "attach_diff_metadata",
    "_enqueue_evidence_snapshot",
    "rag_metrics",
    "deeplink_service",
    "NO_CONTEXT_ANSWER",
]
