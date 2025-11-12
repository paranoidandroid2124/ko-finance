"""Analytics/KPI event ingestion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from schemas.api.analytics import KPIEventRequest, KPIEventResponse
from services.kpi_service import is_allowed_event, record_kpi_event
from web.deps_rbac import RbacState, get_rbac_state

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post(
    "/event",
    response_model=KPIEventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="KPI/캠페인 이벤트를 기록합니다.",
)
async def create_kpi_event(
    payload: KPIEventRequest,
    state: RbacState = Depends(get_rbac_state),
) -> KPIEventResponse:
    if state.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "kpi.user_required", "message": "로그인된 사용자만 KPI 이벤트를 전송할 수 있습니다."},
        )

    if not is_allowed_event(payload.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "kpi.event_not_allowed", "message": f"'{payload.name}' 이벤트는 허용되지 않습니다."},
        )

    record_kpi_event(
        name=payload.name,
        source=payload.source or "campaign",
        payload=payload.payload,
        user_id=state.user_id,
        org_id=state.org_id,
    )
    return KPIEventResponse(status="accepted")


__all__ = ["router"]
