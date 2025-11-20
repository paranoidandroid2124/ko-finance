"""Persistence helpers for generated reports."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from database import SessionLocal
from models.report import Report
from models.report_feedback import ReportFeedback


def _get_session(session: Optional[Session]) -> tuple[Session, bool]:
    if session is not None:
        return session, False
    return SessionLocal(), True


def create_report_record(
    *,
    user_id: UUID,
    org_id: Optional[UUID],
    ticker: str,
    title: Optional[str],
    content_md: str,
    sources: list[dict],
    session: Optional[Session] = None,
) -> Report:
    db, managed = _get_session(session)
    try:
        record = Report(
            user_id=user_id,
            org_id=org_id,
            ticker=ticker,
            title=title,
            content_md=content_md,
            sources=sources,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        raise
    finally:
        if managed:
            db.close()


def list_reports_for_user(
    *,
    user_id: UUID,
    limit: int = 20,
    session: Optional[Session] = None,
) -> List[Report]:
    db, managed = _get_session(session)
    try:
        return (
            db.query(Report)
            .filter(Report.user_id == user_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        if managed:
            db.close()


def get_report_by_id(
    report_id: UUID,
    *,
    session: Optional[Session] = None,
) -> Optional[Report]:
    db, managed = _get_session(session)
    try:
        return db.query(Report).filter(Report.id == report_id).first()
    finally:
        if managed:
            db.close()


def create_report_feedback(
    *,
    report_id: UUID,
    user_id: UUID,
    sentiment: str,
    category: Optional[str] = None,
    comment: Optional[str] = None,
    session: Optional[Session] = None,
) -> ReportFeedback:
    db, managed = _get_session(session)
    try:
        feedback = ReportFeedback(
            report_id=report_id,
            user_id=user_id,
            sentiment=sentiment,
            category=category,
            comment=comment,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback
    except Exception:
        db.rollback()
        raise
    finally:
        if managed:
            db.close()


__all__ = [
    "create_report_record",
    "list_reports_for_user",
    "get_report_by_id",
    "create_report_feedback",
]
