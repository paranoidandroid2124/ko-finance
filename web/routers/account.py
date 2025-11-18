"""Account-level endpoints for legal & data operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.account import DSARRequestCreate, DSARRequestListResponse, DSARRequestSummary
from services.compliance import dsar_service
from services.compliance.dsar_service import DSARRequestRecord, DSARServiceError
from web.deps_rbac import RbacState, get_rbac_state

router = APIRouter(prefix="/account", tags=["Account"])


def _ensure_authenticated(state: RbacState) -> None:
    if state.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "dsar.user_required", "message": "로그인된 사용자만 이용할 수 있습니다."},
        )


def _serialize(record: DSARRequestRecord) -> DSARRequestSummary:
    return DSARRequestSummary(
        id=record.id,
        requestType=record.request_type,
        status=record.status,
        channel=record.channel,
        requestedAt=record.requested_at,
        completedAt=record.completed_at,
        artifactPath=record.artifact_path,
        failureReason=record.failure_reason,
        metadata=record.metadata,
    )


@router.get(
    "/dsar",
    response_model=DSARRequestListResponse,
    summary="내 DSAR 요청 내역을 조회합니다.",
)
def list_dsar_requests(
    limit: int = 20,
    db: Session = Depends(get_db),
    state: RbacState = Depends(get_rbac_state),
) -> DSARRequestListResponse:
    _ensure_authenticated(state)
    safe_limit = max(1, min(limit, 50))
    records = dsar_service.list_requests(db, user_id=state.user_id, limit=safe_limit)
    pending_count = sum(1 for record in records if record.status in {"pending", "processing"})
    return DSARRequestListResponse(
        requests=[_serialize(record) for record in records],
        pendingCount=pending_count,
        hasActiveRequest=pending_count > 0,
    )


@router.post(
    "/dsar",
    response_model=DSARRequestSummary,
    status_code=status.HTTP_201_CREATED,
    summary="DSAR(데이터 내보내기/삭제) 요청을 생성합니다.",
)
def create_dsar_request(
    payload: DSARRequestCreate,
    db: Session = Depends(get_db),
    state: RbacState = Depends(get_rbac_state),
) -> DSARRequestSummary:
    _ensure_authenticated(state)
    try:
        record = dsar_service.create_request(
            db,
            user_id=state.user_id,
            org_id=state.org_id,
            request_type=payload.requestType,
            requested_by=state.user_id,
            note=payload.note,
        )
    except DSARServiceError as exc:
        status_code = status.HTTP_409_CONFLICT if exc.code == "dsar.pending_exists" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return _serialize(record)


__all__ = ["router"]
