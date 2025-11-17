from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from services import workspace_service
from services.workspace_service import WorkspaceMember, WorkspaceNotebook, WorkspaceOverview, WorkspaceWatchlist
from web.deps_rbac import RbacState
from web.routers import workspaces as workspaces_router


def _overview_factory() -> WorkspaceOverview:
    now = datetime.now(timezone.utc)
    org_id = uuid.uuid4()
    return WorkspaceOverview(
        org_id=org_id,
        org_name="테스트 조직",
        member_count=1,
        members=[
            WorkspaceMember(
                user_id=uuid.uuid4(),
                email="alice@example.com",
                name="Alice",
                role="editor",
                status="active",
                joined_at=now,
                accepted_at=now,
            )
        ],
        notebooks=[
            WorkspaceNotebook(
                id=str(uuid.uuid4()),
                title="Deal tracker",
                summary="IR 콜 메모",
                tags=["ir", "watchlist"],
                entry_count=3,
                last_activity_at=now,
            )
        ],
        watchlists=[
            WorkspaceWatchlist(
                rule_id="rule-1",
                name="바이오 워치리스트",
                type="watchlist",
                tickers=["000660"],
                event_count=4,
                updated_at=now,
            )
        ],
    )


def test_read_current_workspace_returns_payload(monkeypatch):
    overview = _overview_factory()
    monkeypatch.setattr(workspaces_router, "get_workspace_overview", lambda *_, **__: overview)
    state = RbacState(
        user_id=uuid.uuid4(),
        org_id=overview.org_id,
        membership=None,
        issue=None,
        enforce_default=False,
    )

    response = workspaces_router.read_current_workspace(db=None, state=state, plan=None)  # type: ignore[arg-type]

    assert response.orgId == overview.org_id
    assert response.members[0].email == "alice@example.com"
    assert response.notebooks[0].entryCount == 3
    assert response.watchlists[0].ruleId == "rule-1"


def test_read_current_workspace_requires_org(monkeypatch):
    state = RbacState(
        user_id=uuid.uuid4(),
        org_id=None,
        membership=None,
        issue=None,
        enforce_default=False,
    )

    with pytest.raises(HTTPException) as exc:
        workspaces_router.read_current_workspace(db=None, state=state, plan=None)  # type: ignore[arg-type]

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "workspace.org_required"
