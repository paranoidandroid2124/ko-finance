"""Workspace overview endpoints (shared watchlists + notebooks)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.workspaces import (
    WorkspaceMemberSchema,
    WorkspaceNotebookSchema,
    WorkspaceOverviewResponse,
    WorkspaceWatchlistSchema,
)
from services.plan_service import PlanContext
from services.workspace_service import get_workspace_overview
from web.deps import require_plan_feature
from web.deps_rbac import RbacState, get_rbac_state

router = APIRouter(prefix="/workspaces", tags=["Workspace"])


def _require_org(state: RbacState) -> None:
    if state.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "workspace.org_required", "message": "X-Org-Id header is required for workspace APIs."},
        )


@router.get("/current", response_model=WorkspaceOverviewResponse)
def read_current_workspace(
    *,
    db: Session = Depends(get_db),
    state: RbacState = Depends(get_rbac_state),
    plan: PlanContext = Depends(require_plan_feature("collab.notebook")),
) -> WorkspaceOverviewResponse:
    _require_org(state)
    overview = get_workspace_overview(db, org_id=state.org_id, user_id=state.user_id, plan=plan)
    return WorkspaceOverviewResponse(
        orgId=overview.org_id,
        orgName=overview.org_name,
        memberCount=overview.member_count,
        members=[
            WorkspaceMemberSchema(
                userId=member.user_id,
                email=member.email,
                name=member.name,
                role=member.role,
                status=member.status,
                joinedAt=member.joined_at,
                acceptedAt=member.accepted_at,
            )
            for member in overview.members
        ],
        notebooks=[
            WorkspaceNotebookSchema(
                id=nb.id,
                title=nb.title,
                summary=nb.summary,
                tags=nb.tags,
                entryCount=nb.entry_count,
                lastActivityAt=nb.last_activity_at,
            )
            for nb in overview.notebooks
        ],
        watchlists=[
            WorkspaceWatchlistSchema(
                ruleId=wl.rule_id,
                name=wl.name,
                type=wl.type,
                tickers=wl.tickers,
                eventCount=wl.event_count,
                updatedAt=wl.updated_at,
            )
            for wl in overview.watchlists
        ],
    )


__all__ = ["router"]
