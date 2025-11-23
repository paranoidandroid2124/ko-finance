"""Helpers for proactive notifications feed (storage + creation)."""

from __future__ import annotations

import uuid
from typing import Iterable, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from models import ProactiveNotification

DEFAULT_LIMIT = 20


def _merged_metadata(existing: Optional[dict], incoming: Optional[dict]) -> Optional[dict]:
    if not incoming:
        return existing
    if not existing:
        return incoming
    if isinstance(existing, dict):
        base = existing.copy()
    else:
        base = {}
    base.update(incoming)
    return base


def upsert_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_id: str,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    ticker: Optional[str] = None,
    target_url: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> ProactiveNotification:
    existing: Optional[ProactiveNotification] = (
        db.query(ProactiveNotification)
        .filter(
            ProactiveNotification.user_id == user_id,
            ProactiveNotification.source_type == source_type,
            ProactiveNotification.source_id == source_id,
        )
        .first()
    )
    if existing:
        existing.title = title or existing.title
        existing.summary = summary or existing.summary
        existing.ticker = ticker or existing.ticker
        existing.target_url = target_url or existing.target_url
        existing.meta = _merged_metadata(existing.meta, metadata)
        existing.status = existing.status or "unread"
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    notif = ProactiveNotification(
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        title=title,
        summary=summary,
        ticker=ticker,
        target_url=target_url,
        meta=metadata,
        status="unread",
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def list_notifications(
    db: Session,
    *,
    user_id: uuid.UUID,
    limit: int = DEFAULT_LIMIT,
    statuses: Optional[Iterable[str]] = None,
) -> List[ProactiveNotification]:
    query = db.query(ProactiveNotification).filter(ProactiveNotification.user_id == user_id)
    if statuses:
        query = query.filter(ProactiveNotification.status.in_(list(statuses)))
    return query.order_by(ProactiveNotification.created_at.desc()).limit(limit).all()


def update_status(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
    status: str,
) -> Optional[ProactiveNotification]:
    updated = (
        db.query(ProactiveNotification)
        .filter(
            and_(
                ProactiveNotification.id == notification_id,
                ProactiveNotification.user_id == user_id,
            )
        )
        .first()
    )
    if not updated:
        return None
    updated.status = status
    db.add(updated)
    db.commit()
    db.refresh(updated)
    return updated


__all__ = ["upsert_notification", "list_notifications", "update_status"]
