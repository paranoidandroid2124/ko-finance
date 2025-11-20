"""Admin endpoints for user monitoring and controls."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from database import get_db
from models import Report, ReportFeedback
from schemas.api.admin import (
    AdminKpiResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from web.deps import require_admin_user

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin_user)])


@router.get("/kpi", response_model=AdminKpiResponse)
def read_admin_kpi(db: Session = Depends(get_db)) -> AdminKpiResponse:
    total_users = db.query(func.count(User.id)).scalar() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    reports_today = (
        db.query(func.count(Report.id))
        .filter(Report.created_at >= today_start)
        .scalar()
        or 0
    )

    heavy_users = (
        db.query(func.count(Report.user_id))
        .filter(Report.created_at >= datetime.utcnow() - timedelta(days=7))
        .group_by(Report.user_id)
        .having(func.count(Report.id) >= 5)
        .count()
    )

    return AdminKpiResponse(totalUsers=total_users, reportsToday=reports_today, heavyUsers=heavy_users)


@router.get("/users", response_model=AdminUserListResponse)
def list_admin_users(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AdminUserListResponse:
    reports_subquery = (
        db.query(
            Report.user_id.label("user_id"),
            func.count(Report.id).label("report_count"),
            func.max(Report.created_at).label("last_report_at"),
        )
        .group_by(Report.user_id)
        .subquery()
    )

    stmt = text(
        """
        SELECT
            u.id,
            u.email,
            COALESCE(u.plan_tier, 'free') AS plan_tier,
            COALESCE(u.is_active, TRUE) AS is_active,
            u.last_login_at,
            COALESCE(r.report_count, 0) AS report_count,
            r.last_report_at
        FROM users u
        LEFT JOIN (
            SELECT user_id, COUNT(*) AS report_count, MAX(created_at) AS last_report_at
            FROM reports
            GROUP BY user_id
        ) AS r ON u.id = r.user_id
        ORDER BY r.report_count DESC NULLS LAST, u.created_at DESC
        LIMIT :limit
        """
    )
    rows = db.execute(stmt, {"limit": limit}).mappings().all()

    users = [
        AdminUserResponse(
            id=str(row["id"]),
            email=row["email"],
            plan=row["plan_tier"],
            isActive=bool(row["is_active"]),
            reportCount=int(row["report_count"] or 0),
            lastReportAt=row.get("last_report_at"),
            lastLoginAt=row.get("last_login_at"),
        )
        for row in rows
    ]
    return AdminUserListResponse(users=users)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_admin_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    existing = db.execute(text('SELECT * FROM users WHERE id = :id'), {"id": str(user_id)}).mappings().first()
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if payload.plan:
        db.execute(
            text("UPDATE users SET plan_tier = :plan WHERE id = :id"),
            {"plan": payload.plan, "id": str(user_id)},
        )
    if payload.isActive is not None:
        db.execute(
            text("UPDATE users SET is_active = :active WHERE id = :id"),
            {"active": payload.isActive, "id": str(user_id)},
        )
    db.commit()

    refreshed = db.execute(text('SELECT * FROM users WHERE id = :id'), {"id": str(user_id)}).mappings().first()
    report_count, last_report_at = (
        db.query(func.count(Report.id), func.max(Report.created_at))
        .filter(Report.user_id == uuid.UUID(str(user_id)))
        .first()
    )

    return AdminUserResponse(
        id=str(refreshed["id"]),
        email=refreshed["email"],
        plan=refreshed.get("plan_tier") or "free",
        isActive=bool(refreshed.get("is_active", True)),
        reportCount=report_count or 0,
        lastReportAt=last_report_at,
        lastLoginAt=refreshed.get("last_login_at"),
    )
