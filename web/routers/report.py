"""FastAPI router exposing secured report generation and history APIs."""

from __future__ import annotations

import uuid
from typing import List

import io
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from schemas.api.report import (
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportExportRequest,
    ReportHistoryItem,
    ReportHistoryResponse,
    ReportSourceSchema,
)
from services.plan_service import PlanContext
from services.report_service import ReportMemoResult, ReportService
from services import report_repository, report_export_service
from services.web_utils import parse_uuid
from web.deps import require_plan_feature
from web.middleware.auth_context import AuthenticatedUser
from web.quota_guard import enforce_quota

router = APIRouter(prefix="/report", tags=["Report"])
report_service = ReportService()


def _require_user(request: Request) -> AuthenticatedUser:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.required", "message": "로그인이 필요한 요청입니다."},
        )
    return user


def _coerce_uuid(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _serialize_sources(result: List[dict]) -> List[ReportSourceSchema]:
    return [ReportSourceSchema(**entry) for entry in result]


@router.post(
    "/generate",
    response_model=ReportGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_report(
    payload: ReportGenerateRequest,
    request: Request,
    plan: PlanContext = Depends(require_plan_feature("report.create")),
) -> ReportGenerateResponse:
    ticker = payload.ticker.strip()
    if not ticker:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ticker is required")

    user = _require_user(request)
    user_uuid = _coerce_uuid(user.id)
    org_uuid = parse_uuid(request.headers.get("x-org-id"))

    enforce_quota("report.create", plan=plan, user_id=user_uuid, org_id=org_uuid, cost=10)

    try:
        result: ReportMemoResult = await report_service.generate_investment_memo(
            ticker,
            user_id=user_uuid,
            org_id=org_uuid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - network/LLM failures
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="report_generation_failed") from exc

    return ReportGenerateResponse(
        reportId=str(result.report_id) if result.report_id else None,
        ticker=ticker,
        content=result.content,
        sources=_serialize_sources(result.sources),
        charts=result.chart_payload,
    )


@router.get(
    "/history",
    response_model=ReportHistoryResponse,
)
def list_history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    plan: PlanContext = Depends(require_plan_feature("report.create")),
) -> ReportHistoryResponse:
    _ = plan  # dependency ensures entitlement; value unused
    _require_user(request)
    user_uuid = parse_uuid(request.headers.get("x-user-id")) or _coerce_uuid(getattr(request.state.user, "id", None))
    if user_uuid is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-User-Id header.")

    records = report_repository.list_reports_for_user(user_id=user_uuid, limit=limit)
    items = [
        ReportHistoryItem(
            id=str(record.id),
            ticker=record.ticker,
            title=record.title,
            content=record.content_md,
            sources=_serialize_sources(record.sources or []),
            createdAt=record.created_at,
        )
        for record in records
    ]
    return ReportHistoryResponse(items=items)


@router.post("/{report_id}/export")
def export_report(
    report_id: uuid.UUID,
    payload: ReportExportRequest,
    request: Request,
    plan: PlanContext = Depends(require_plan_feature("report.create")),
) -> StreamingResponse:
    _ = plan
    user = _require_user(request)
    record = report_repository.get_report_by_id(report_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    if str(record.user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")

    format_value = (payload.format or "").lower()
    if format_value not in {"pdf", "docx"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format.")

    title = record.title or f"Investment Memo {record.ticker}"
    sources = record.sources or []

    if format_value == "pdf":
        content_bytes = report_export_service.export_pdf(
            title=title,
            markdown_body=record.content_md,
            sources=sources,
            chart_image=payload.chartImage,
        )
        media_type = "application/pdf"
        extension = "pdf"
    else:
        content_bytes = report_export_service.export_docx(
            title=title,
            markdown_body=record.content_md,
            sources=sources,
            chart_image=payload.chartImage,
        )
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        extension = "docx"

    filename = f"{record.ticker or 'investment_memo'}.{extension}"
    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
