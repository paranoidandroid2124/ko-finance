"""Shared helpers for DB-backed audit logging (AuditLog v1)."""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import JSONB

from core.env import env_str

try:  # pragma: no cover - runtime import
    from database import SessionLocal as _SessionLocal
except Exception:  # pragma: no cover
    _SessionLocal = None

logger = logging.getLogger(__name__)

_IP_HASH_SALT = env_str("AUDIT_LOG_IP_SALT") or env_str("AUDIT_LOG_HASH_SALT") or ""
_PARTITION_LOCK = threading.Lock()
_KNOWN_PARTITIONS: set[str] = set()


def _session_factory() -> Session:
    if _SessionLocal is None:  # pragma: no cover
        raise RuntimeError("SessionLocal is unavailable. DATABASE_URL must be configured.")
    return _SessionLocal()


def _hash_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    payload = f"{ip}|{_IP_HASH_SALT}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _month_range(ts: datetime) -> tuple[datetime, datetime]:
    start = datetime(ts.year, ts.month, 1, tzinfo=timezone.utc)
    if ts.month == 12:
        end = datetime(ts.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(ts.year, ts.month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _ensure_partition(session: Session, ts: datetime) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    month_key = ts.strftime("%Y_%m")
    with _PARTITION_LOCK:
        if month_key in _KNOWN_PARTITIONS:
            return
        start, end = _month_range(ts)
        table_name = f"audit_logs_{month_key}"
        session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name}
                PARTITION OF audit_logs
                FOR VALUES FROM (:start_ts) TO (:end_ts)
                """
            ),
            {"start_ts": start, "end_ts": end},
        )
        _KNOWN_PARTITIONS.add(month_key)


def record_audit_event(
    *,
    action: str,
    source: str,
    user_id: Optional[uuid.UUID] = None,
    org_id: Optional[uuid.UUID] = None,
    target_id: Optional[str] = None,
    feature_flags: Optional[Mapping[str, Any]] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    """Persist an audit record into the audit_logs partitioned table."""
    try:
        session = _session_factory()
    except RuntimeError:
        logger.debug("Audit logging skipped because SessionLocal is unavailable.")
        return

    ts = datetime.now(timezone.utc)
    payload = {
        "ts": ts,
        "user_id": user_id,
        "org_id": org_id,
        "action": action,
        "target_id": target_id,
        "source": source,
        "ua": user_agent,
        "ip_hash": _hash_ip(ip),
        "feature_flags": feature_flags or {},
        "extra": extra or {},
    }

    try:
        _ensure_partition(session, ts)
        insert_stmt = (
            text(
                """
                INSERT INTO audit_logs (ts, user_id, org_id, action, target_id, source, ua, ip_hash, feature_flags, extra)
                VALUES (:ts, :user_id, :org_id, :action, :target_id, :source, :ua, :ip_hash, :feature_flags, :extra)
                """
            )
            .bindparams(bindparam("feature_flags", type_=JSONB))
            .bindparams(bindparam("extra", type_=JSONB))
        )
        session.execute(insert_stmt, payload)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Failed to persist audit log event action=%s source=%s.", action, source)
    finally:
        session.close()


# Convenience wrappers --------------------------------------------------------

def audit_ingest_event(
    *,
    action: str,
    target_id: Optional[str],
    extra: Optional[Mapping[str, Any]] = None,
    feature_flags: Optional[Mapping[str, Any]] = None,
) -> None:
    record_audit_event(
        action=action,
        source="ingest",
        target_id=target_id,
        extra=extra,
        feature_flags=feature_flags,
    )


def audit_rag_event(
    *,
    action: str,
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
    target_id: Optional[str],
    feature_flags: Optional[Mapping[str, Any]] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    record_audit_event(
        action=action,
        source="rag",
        user_id=user_id,
        org_id=org_id,
        target_id=target_id,
        feature_flags=feature_flags,
        extra=extra,
    )


def audit_billing_event(
    *,
    action: str,
    org_id: Optional[uuid.UUID],
    target_id: Optional[str],
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    record_audit_event(action=action, source="billing", org_id=org_id, target_id=target_id, extra=extra)


def audit_rbac_event(
    *,
    action: str,
    actor: Optional[str],
    org_id: Optional[uuid.UUID],
    target_id: Optional[str],
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    record_audit_event(
        action=action,
        source="rbac",
        user_id=None,
        org_id=org_id,
        target_id=target_id,
        extra={**({"actor": actor} if actor else {}), **(extra or {})},
    )


def audit_alert_event(
    *,
    action: str,
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
    target_id: Optional[str],
    feature_flags: Optional[Mapping[str, Any]] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    record_audit_event(
        action=action,
        source="alerts",
        user_id=user_id,
        org_id=org_id,
        target_id=target_id,
        feature_flags=feature_flags,
        extra=extra,
    )


def audit_collab_event(
    *,
    action: str,
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
    target_id: Optional[str],
    feature_flags: Optional[Mapping[str, Any]] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    record_audit_event(
        action=action,
        source="collab",
        user_id=user_id,
        org_id=org_id,
        target_id=target_id,
        feature_flags=feature_flags,
        extra=extra,
    )


__all__ = [
    "audit_billing_event",
    "audit_ingest_event",
    "audit_alert_event",
    "audit_rag_event",
    "audit_rbac_event",
    "audit_collab_event",
    "record_audit_event",
]
