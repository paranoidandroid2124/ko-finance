"""Centralised data retention helpers for audit, chat, and evidence logs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.env import env_int
from core.logging import get_logger
from database import SessionLocal
from services.audit_log import record_audit_event

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _retention_days(env_key: str, default: int, *, minimum: int = 0) -> int:
    """Load retention window while allowing overrides via env."""
    return max(env_int(env_key, default, minimum=minimum), 0)


def _execute_delete(session: Session, sql: str, params: Optional[dict] = None) -> int:
    result = session.execute(text(sql), params or {})
    return max(result.rowcount or 0, 0)


def _purge_audit_logs(session: Session, now: datetime) -> int:
    days = _retention_days("RETENTION_AUDIT_LOG_DAYS", 730)
    if days == 0:
        return 0
    cutoff = now - timedelta(days=days)
    return _execute_delete(session, "DELETE FROM audit_logs WHERE ts < :cutoff", {"cutoff": cutoff})


def _purge_chat_content(session: Session, now: datetime) -> int:
    days = _retention_days("RETENTION_CHAT_SESSION_DAYS", 180)
    if days == 0:
        return 0
    cutoff = now - timedelta(days=days)
    deleted = 0
    deleted += _execute_delete(
        session,
        """
        WITH stale AS (
            SELECT id FROM chat_sessions
            WHERE archived_at IS NOT NULL
              AND archived_at < :cutoff
        )
        DELETE FROM chat_messages
        WHERE session_id IN (SELECT id FROM stale)
        """,
        {"cutoff": cutoff},
    )
    deleted += _execute_delete(
        session,
        "DELETE FROM chat_messages_archive WHERE archived_at < :cutoff",
        {"cutoff": cutoff},
    )
    deleted += _execute_delete(
        session,
        "DELETE FROM chat_sessions WHERE archived_at IS NOT NULL AND archived_at < :cutoff",
        {"cutoff": cutoff},
    )
    return deleted


def _purge_chat_audit(session: Session, now: datetime) -> int:
    days = _retention_days("RETENTION_CHAT_AUDIT_DAYS", 365)
    if days == 0:
        return 0
    cutoff = now - timedelta(days=days)
    return _execute_delete(session, "DELETE FROM chat_audit WHERE created_at < :cutoff", {"cutoff": cutoff})


def _purge_alert_logs(session: Session, now: datetime) -> int:
    days = _retention_days("RETENTION_ALERT_DELIVERY_DAYS", 365)
    if days == 0:
        return 0
    cutoff = now - timedelta(days=days)
    return _execute_delete(
        session,
        "DELETE FROM alert_deliveries WHERE created_at < :cutoff",
        {"cutoff": cutoff},
    )


def _purge_evidence_snapshots(session: Session, now: datetime) -> int:
    days = _retention_days("RETENTION_EVIDENCE_SNAPSHOT_DAYS", 365)
    if days == 0:
        return 0
    cutoff = now - timedelta(days=days)
    return _execute_delete(
        session,
        "DELETE FROM evidence_snapshots WHERE updated_at < :cutoff",
        {"cutoff": cutoff},
    )


def apply_retention_policies(*, now: Optional[datetime] = None) -> Dict[str, int]:
    """Trim persisted data according to compliance retention windows."""
    session = SessionLocal()
    snapshot = now or _utcnow()
    stats: Dict[str, int] = {}
    try:
        with session.begin():
            stats["audit_logs"] = _purge_audit_logs(session, snapshot)
            stats["chat"] = _purge_chat_content(session, snapshot)
            stats["chat_audit"] = _purge_chat_audit(session, snapshot)
            stats["alert_deliveries"] = _purge_alert_logs(session, snapshot)
            stats["evidence_snapshots"] = _purge_evidence_snapshots(session, snapshot)
    except SQLAlchemyError:
        logger.exception("Data retention job failed; rolling back changes.")
        session.rollback()
        raise
    finally:
        session.close()

    total_deleted = sum(stats.values())
    if total_deleted:
        logger.info("Retention job removed %d stale rows: %s", total_deleted, stats)
        record_audit_event(
            action="compliance.retention",
            source="compliance",
            extra={"deleted": stats, "total": total_deleted},
        )
    else:
        logger.debug("Retention job finished. No stale rows matched configured cutoffs.")
    return stats


__all__ = ["apply_retention_policies"]
