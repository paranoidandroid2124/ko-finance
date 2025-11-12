"""Admin session issuance, validation, and auditing helpers."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.env import env_bool, env_int, env_str
from core.logging import get_logger

logger = get_logger(__name__)

UTC = timezone.utc
_SESSION_TTL_SECONDS = env_int("ADMIN_SESSION_TTL_SECONDS", 60 * 60 * 24, minimum=300)
SESSION_COOKIE_NAME = env_str("ADMIN_SESSION_COOKIE_NAME", "admin_session") or "admin_session"
SESSION_COOKIE_SAMESITE = (env_str("ADMIN_SESSION_COOKIE_SAMESITE", "Lax") or "Lax").capitalize()
SESSION_COOKIE_SECURE = env_bool("ADMIN_SESSION_COOKIE_SECURE", False)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return "*" * len(token)
    return f"{token[:2]}***{token[-2:]}"


@dataclass(frozen=True)
class AdminSessionRecord:
    id: str
    actor: str
    issued_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    ip: Optional[str]
    user_agent: Optional[str]
    token_hint: Optional[str]


@dataclass(frozen=True)
class AdminSessionIssueResult:
    token: str
    record: AdminSessionRecord


def _row_to_record(row: Dict[str, Any]) -> AdminSessionRecord:
    return AdminSessionRecord(
        id=str(row["id"]),
        actor=row["actor"],
        issued_at=row["created_at"],
        expires_at=row["expires_at"],
        last_seen_at=row["last_seen_at"],
        ip=row.get("ip"),
        user_agent=row.get("user_agent"),
        token_hint=row.get("token_hint"),
    )


def issue_admin_session(
    db: Session,
    *,
    actor: str,
    ip: Optional[str],
    user_agent: Optional[str],
    ttl_seconds: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AdminSessionIssueResult:
    """Persist a new admin session and return the opaque token."""

    token = secrets.token_urlsafe(48)
    digest = _token_digest(token)
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=ttl_seconds or _SESSION_TTL_SECONDS)
    payload = {
        "actor": actor,
        "token_hash": digest,
        "ip": ip,
        "user_agent": user_agent,
        "expires_at": expires_at,
        "metadata": json.dumps(metadata or {}),
    }
    row = (
        db.execute(
            text(
                """
                INSERT INTO admin_sessions (actor, token_hash, ip, user_agent, expires_at, metadata)
                VALUES (:actor, :token_hash, :ip, :user_agent, :expires_at, CAST(:metadata AS JSONB))
                RETURNING id, actor, created_at, expires_at, last_seen_at, ip, user_agent
                """
            ),
            payload,
        )
        .mappings()
        .first()
    )
    if not row:
        raise RuntimeError("Failed to create admin session.")
    db.commit()
    record = AdminSessionRecord(
        id=str(row["id"]),
        actor=row["actor"],
        issued_at=row["created_at"],
        expires_at=row["expires_at"],
        last_seen_at=row["last_seen_at"],
        ip=row.get("ip"),
        user_agent=row.get("user_agent"),
        token_hint=f"sid:{str(row['id'])[:8]}",
    )
    logger.info("Issued admin session for actor=%s session_id=%s.", actor, record.id)
    return AdminSessionIssueResult(token=token, record=record)


def validate_admin_session(
    db: Session,
    *,
    token: str,
    touch: bool = True,
) -> Optional[AdminSessionRecord]:
    """Validate an opaque admin session token."""

    digest = _token_digest(token)
    row = (
        db.execute(
            text(
                """
                SELECT id, actor, created_at, expires_at, last_seen_at, ip, user_agent, revoked_at
                FROM admin_sessions
                WHERE token_hash = :token_hash
                """
            ),
            {"token_hash": digest},
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    if row["revoked_at"]:
        return None
    now = datetime.now(UTC)
    if row["expires_at"] < now:
        return None
    record = AdminSessionRecord(
        id=str(row["id"]),
        actor=row["actor"],
        issued_at=row["created_at"],
        expires_at=row["expires_at"],
        last_seen_at=row["last_seen_at"],
        ip=row.get("ip"),
        user_agent=row.get("user_agent"),
        token_hint=f"sid:{str(row['id'])[:8]}",
    )
    if touch:
        db.execute(
            text(
                """
                UPDATE admin_sessions
                SET last_seen_at = NOW()
                WHERE id = :session_id
                """
            ),
            {"session_id": record.id},
        )
        db.commit()
    return record


def revoke_admin_session(
    db: Session,
    *,
    token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> bool:
    """Revoke an existing admin session."""

    if not token and not session_id:
        raise ValueError("token or session_id is required to revoke an admin session.")
    clause = ""
    params: Dict[str, Any] = {}
    if session_id:
        clause = "id = :session_id"
        params["session_id"] = session_id
    else:
        clause = "token_hash = :token_hash"
        params["token_hash"] = _token_digest(token or "")

    result = db.execute(
        text(
            f"""
            UPDATE admin_sessions
            SET revoked_at = COALESCE(revoked_at, NOW())
            WHERE {clause}
              AND revoked_at IS NULL
            RETURNING id
            """
        ),
        params,
    )
    db.commit()
    row = result.mappings().first()
    return bool(row)


def record_admin_audit_event(
    db: Session,
    *,
    actor: str,
    event_type: str,
    session_id: Optional[str],
    route: Optional[str],
    method: Optional[str],
    ip: Optional[str],
    user_agent: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist an audit trail entry for admin operations."""

    db.execute(
        text(
            """
            INSERT INTO admin_audit_logs (session_id, actor, event_type, route, method, ip, user_agent, metadata)
            VALUES (:session_id, :actor, :event_type, :route, :method, :ip, :user_agent, CAST(:metadata AS JSONB))
            """
        ),
        {
            "session_id": session_id,
            "actor": actor,
            "event_type": event_type,
            "route": route,
            "method": method,
            "ip": ip,
            "user_agent": user_agent,
            "metadata": json.dumps(metadata or {}),
        },
    )
    db.commit()
    logger.debug("Recorded admin audit event %s for actor=%s.", event_type, actor)
