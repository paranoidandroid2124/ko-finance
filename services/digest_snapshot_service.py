"""Helpers for storing and retrieving digest snapshot payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.digest import DigestSnapshot

DEFAULT_CHANNEL = "dashboard"


def _match_nullable(column, value):
    return column.is_(None) if value is None else column == value


def upsert_snapshot(
    session: Session,
    *,
    digest_date,
    timeframe: str,
    payload: Dict[str, Any],
    user_id: Optional[UUID] = None,
    org_id: Optional[UUID] = None,
    channel: str = DEFAULT_CHANNEL,
    llm_model: Optional[str] = None,
) -> DigestSnapshot:
    """Create or update a snapshot for the given scope."""

    snapshot = (
        session.query(DigestSnapshot)
        .filter(
            DigestSnapshot.digest_date == digest_date,
            DigestSnapshot.timeframe == timeframe,
            DigestSnapshot.channel == channel,
            _match_nullable(DigestSnapshot.user_id, user_id),
            _match_nullable(DigestSnapshot.org_id, org_id),
        )
        .one_or_none()
    )

    if snapshot is None:
        snapshot = DigestSnapshot(
            digest_date=digest_date,
            timeframe=timeframe,
            channel=channel,
            user_id=user_id,
            org_id=org_id,
            payload=payload,
            llm_model=llm_model,
        )
        session.add(snapshot)
    else:
        snapshot.payload = payload
        snapshot.llm_model = llm_model or snapshot.llm_model
        snapshot.updated_at = datetime.now(timezone.utc)
    session.flush()
    return snapshot


def load_snapshot(
    session: Session,
    *,
    timeframe: str,
    reference_date=None,
    user_id: Optional[str] = None,
    org_id: Optional[UUID] = None,
    channel: str = DEFAULT_CHANNEL,
) -> Optional[Dict[str, Any]]:
    """Return the latest snapshot payload for the specified scope."""

    query = (
        session.query(DigestSnapshot)
        .filter(
            DigestSnapshot.timeframe == timeframe,
            DigestSnapshot.channel == channel,
        )
        .order_by(DigestSnapshot.digest_date.desc(), DigestSnapshot.updated_at.desc())
    )

    if reference_date is not None:
        query = query.filter(DigestSnapshot.digest_date == reference_date)

    query = query.filter(
        _match_nullable(DigestSnapshot.user_id, user_id),
        _match_nullable(DigestSnapshot.org_id, org_id),
    )

    snapshot = query.first()
    if snapshot is None:
        return None
    return snapshot.payload


__all__ = ["upsert_snapshot", "load_snapshot"]
