"""FastAPI routes for the Interactive Analyst (RAG) module."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
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
from services import rag_service
from web.deps import require_plan_feature

router = APIRouter(prefix="/rag", tags=["RAG"])


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
    return rag_service.query_rag(request, x_user_id, x_org_id, idempotency_key_header, plan, db)


@router.post("/query/stream")
def query_rag_stream(
    request: RAGQueryRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    idempotency_key_header: Optional[str] = Header(default=None, convert_underscores=False, alias="Idempotency-Key"),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    return rag_service.query_rag_stream(request, x_user_id, x_org_id, idempotency_key_header, plan, db)


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
    return rag_service.query_rag_v2(payload, x_user_id, x_org_id, plan, db)


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


__all__ = ["router"]
