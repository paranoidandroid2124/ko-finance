"""Workspace aggregation helpers that combine org memberships, notebooks, and watchlists."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from services import notebook_service
from services.plan_service import PlanContext
from services.rbac_service import rbac_service
from services.watchlist_aggregator import collect_watchlist_items, summarise_watchlist_rules

MEMBER_SELECT = text(
    """
    SELECT uo.user_id,
           uo.role_key,
           uo.status,
           uo.created_at,
           uo.accepted_at,
           u.email,
           u.name
    FROM user_orgs uo
    LEFT JOIN users u ON u.id = uo.user_id
    WHERE uo.org_id = :org_id
    ORDER BY uo.created_at ASC
    LIMIT :limit
    """
)


@dataclass(slots=True)
class WorkspaceMember:
    user_id: uuid.UUID
    email: Optional[str]
    name: Optional[str]
    role: str
    status: str
    joined_at: Optional[datetime]
    accepted_at: Optional[datetime]


@dataclass(slots=True)
class WorkspaceNotebook:
    id: str
    title: str
    summary: Optional[str]
    tags: List[str]
    entry_count: int
    last_activity_at: Optional[datetime]


@dataclass(slots=True)
class WorkspaceWatchlist:
    rule_id: str
    name: str
    type: str
    tickers: List[str] = field(default_factory=list)
    event_count: int = 0
    updated_at: Optional[datetime] = None


@dataclass(slots=True)
class WorkspaceOverview:
    org_id: uuid.UUID
    org_name: Optional[str]
    member_count: int
    members: List[WorkspaceMember]
    notebooks: List[WorkspaceNotebook]
    watchlists: List[WorkspaceWatchlist]
    plan: Optional[PlanContext] = None


def _convert_member(row: Mapping[str, Any]) -> WorkspaceMember:
    return WorkspaceMember(
        user_id=row["user_id"],
        email=row.get("email"),
        name=row.get("name"),
        role=str(row.get("role_key") or "viewer"),
        status=str(row.get("status") or "active"),
        joined_at=row.get("created_at"),
        accepted_at=row.get("accepted_at"),
    )


def _load_members(db: Session, *, org_id: uuid.UUID, limit: int = 50) -> List[WorkspaceMember]:
    rows = db.execute(MEMBER_SELECT, {"org_id": str(org_id), "limit": int(limit)}).mappings()
    return [_convert_member(row) for row in rows]


def _convert_notebooks(records: Sequence[notebook_service.NotebookRecord]) -> List[WorkspaceNotebook]:
    notebooks: List[WorkspaceNotebook] = []
    for record in records:
        notebooks.append(
            WorkspaceNotebook(
                id=str(record.id),
                title=record.title,
                summary=record.summary,
                tags=list(record.tags or []),
                entry_count=record.entry_count,
                last_activity_at=record.last_activity_at,
            )
        )
    return notebooks


def _convert_watchlists(items: Sequence[Mapping[str, Any]]) -> List[WorkspaceWatchlist]:
    summaries = summarise_watchlist_rules(items)
    converted: List[WorkspaceWatchlist] = []
    for summary in summaries:
        converted.append(
            WorkspaceWatchlist(
                rule_id=summary.rule_id,
                name=summary.name,
                type="watchlist",
                tickers=sorted(summary.tickers),
                event_count=summary.event_count,
                updated_at=summary.last_triggered_at,
            )
        )
    return converted


def get_workspace_overview(
    db: Session,
    *,
    org_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    plan: Optional[PlanContext] = None,
    notebook_limit: int = 5,
    watchlist_limit: int = 10,
) -> WorkspaceOverview:
    org_record = rbac_service.get_org(org_id)
    members = _load_members(db, org_id=org_id)
    notebooks = notebook_service.list_notebooks(db, org_id=org_id, query=None, tags=None, limit=notebook_limit)
    watchlist_items, _ = collect_watchlist_items(
        db,
        user_id=user_id,
        org_id=org_id,
        limit=watchlist_limit,
        window_minutes=1440,
    )

    return WorkspaceOverview(
        org_id=org_id,
        org_name=org_record.name if org_record else None,
        member_count=len(members),
        members=members,
        notebooks=_convert_notebooks(notebooks),
        watchlists=_convert_watchlists(watchlist_items),
        plan=plan,
    )


__all__ = [
    "WorkspaceMember",
    "WorkspaceNotebook",
    "WorkspaceOverview",
    "WorkspaceWatchlist",
    "get_workspace_overview",
]
