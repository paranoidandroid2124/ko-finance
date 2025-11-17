from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.dashboard import DashboardOverviewResponse, FilingTrendResponse
from services.dashboard_service import (
    DashboardRequestContext,
    build_dashboard_overview,
    generate_filing_trend,
)
from web.deps_rbac import RbacState, get_rbac_state

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview", response_model=DashboardOverviewResponse)
def read_dashboard_overview(
    db: Session = Depends(get_db),
    state: RbacState = Depends(get_rbac_state),
) -> DashboardOverviewResponse:
    context = DashboardRequestContext(user_id=state.user_id, org_id=state.org_id)
    return build_dashboard_overview(db, context=context)


@router.get("/filing-trend", response_model=FilingTrendResponse)
def read_filing_trend(days: int = 7, db: Session = Depends(get_db)) -> FilingTrendResponse:
    return generate_filing_trend(db, days=days)
