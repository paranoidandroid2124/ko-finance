"""Helpers for data subject access request (DSAR) intake and processing."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.logging import get_logger
from database import SessionLocal
from models.alert import AlertRule
from models.chat import ChatMessage, ChatMessageArchive, ChatSession
from models.digest import DigestSnapshot
from models.dsar import DSARRequest
from models.notebook import Notebook, NotebookEntry, NotebookShare
from services.audit_log import record_audit_event
from services import user_settings_service

logger = get_logger(__name__)

DSAR_EXPORT_ROOT = Path(os.getenv("DSAR_EXPORT_DIR", "uploads/dsar"))
AUDIT_EXPORT_LIMIT = int(os.getenv("DSAR_AUDIT_EXPORT_LIMIT", "500"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _normalize_uuid(value: Optional[uuid.UUID]) -> Optional[str]:
    return str(value) if value else None


@dataclass(frozen=True)
class DSARRequestRecord:
    id: uuid.UUID
    request_type: str
    status: str
    channel: str
    requested_at: datetime
    completed_at: Optional[datetime]
    artifact_path: Optional[str]
    failure_reason: Optional[str]
    metadata: Dict[str, Any]


class DSARServiceError(Exception):
    """Base error for DSAR operations."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _to_record(model: DSARRequest) -> DSARRequestRecord:
    return DSARRequestRecord(
        id=model.id,
        request_type=model.request_type,
        status=model.status,
        channel=model.channel,
        requested_at=model.requested_at,
        completed_at=model.completed_at,
        artifact_path=model.artifact_path,
        failure_reason=model.failure_reason,
        metadata=dict(model.metadata or {}),
    )


def list_requests(
    session: Session,
    *,
    user_id: uuid.UUID,
    limit: int = 20,
) -> List[DSARRequestRecord]:
    query = (
        session.query(DSARRequest)
        .filter(DSARRequest.user_id == user_id)
        .order_by(DSARRequest.requested_at.desc())
        .limit(limit)
    )
    return [_to_record(row) for row in query.all()]


def create_request(
    session: Session,
    *,
    user_id: uuid.UUID,
    org_id: Optional[uuid.UUID],
    request_type: str,
    channel: str = "self_service",
    requested_by: Optional[uuid.UUID] = None,
    note: Optional[str] = None,
) -> DSARRequestRecord:
    """Persist a new DSAR request if no conflicting one exists."""
    active = (
        session.query(DSARRequest)
        .filter(
            DSARRequest.user_id == user_id,
            DSARRequest.status.in_(("pending", "processing")),
        )
        .count()
    )
    if active:
        raise DSARServiceError("dsar.pending_exists", "이미 처리 중인 요청이 있습니다.")

    metadata = {}
    if note:
        metadata["note"] = note

    request = DSARRequest(
        user_id=user_id,
        org_id=org_id,
        request_type=request_type,
        channel=channel,
        requested_by=requested_by,
        metadata=metadata,
    )
    session.add(request)
    session.commit()
    record_audit_event(
        action="dsar.request.created",
        source="compliance",
        user_id=user_id,
        org_id=org_id,
        target_id=str(request.id),
        extra={"request_type": request_type, "channel": channel},
    )
    return _to_record(request)


def process_pending_requests(limit: int = 5) -> Dict[str, int]:
    """Claim pending DSAR requests and execute export/delete flows."""
    session = SessionLocal()
    stats = {"claimed": 0, "completed": 0, "failed": 0}
    now = _utcnow()
    pending_ids: List[uuid.UUID] = []
    try:
        with session.begin():
            pending_ids = [
                row.id
                for row in (
                    session.query(DSARRequest.id)
                    .filter(DSARRequest.status == "pending")
                    .order_by(DSARRequest.requested_at.asc())
                    .with_for_update(skip_locked=True)
                    .limit(limit)
                    .all()
                )
            ]
            for request_id in pending_ids:
                request = session.get(DSARRequest, request_id)
                if not request:
                    continue
                request.status = "processing"
                request.started_at = now
            stats["claimed"] = len(pending_ids)

        for request_id in pending_ids:
            _process_single_request(session, request_id, stats)
    finally:
        session.close()
    return stats


def _process_single_request(session: Session, request_id: uuid.UUID, stats: Dict[str, int]) -> None:
    request = session.get(DSARRequest, request_id)
    if request is None:
        return
    try:
        if request.request_type == "export":
            artifact_path, meta = _run_export(session, request)
            request.artifact_path = artifact_path
        else:
            meta = _run_deletion(session, request)
            request.artifact_path = None
        current_meta = dict(request.metadata or {})
        current_meta.update(meta)
        request.metadata = current_meta
        request.status = "completed"
        request.completed_at = _utcnow()
        request.failure_reason = None
        session.commit()
        stats["completed"] += 1
        record_audit_event(
            action=f"dsar.request.{request.request_type}.completed",
            source="compliance",
            user_id=request.user_id,
            org_id=request.org_id,
            target_id=str(request.id),
            extra={"request_type": request.request_type},
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        session.rollback()
        request = session.get(DSARRequest, request_id)
        if request:
            request.status = "failed"
            request.failure_reason = str(exc)
            request.completed_at = _utcnow()
            session.commit()
            stats["failed"] += 1
            record_audit_event(
                action="dsar.request.failed",
                source="compliance",
                user_id=request.user_id,
                org_id=request.org_id,
                target_id=str(request.id),
                extra={"error": str(exc)},
            )
        logger.exception("DSAR request %s failed: %s", request_id, exc)


def _run_export(session: Session, request: DSARRequest) -> Tuple[str, Dict[str, Any]]:
    payload, counts = _build_export_payload(session, request)
    DSAR_EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    artifact = DSAR_EXPORT_ROOT / f"{request.id}_export.json"
    artifact.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    size_bytes = artifact.stat().st_size if artifact.exists() else 0
    meta = {
        "resourceCounts": counts,
        "artifactBytes": size_bytes,
        "artifactPath": str(artifact),
    }
    return str(artifact), meta


def _build_export_payload(session: Session, request: DSARRequest) -> Tuple[Dict[str, Any], Dict[str, int]]:
    counts: Dict[str, int] = {}
    user_id = request.user_id
    org_id = request.org_id
    payload: Dict[str, Any] = {
        "requestId": str(request.id),
        "generatedAt": _utcnow().isoformat(),
        "requestType": request.request_type,
        "userId": _normalize_uuid(user_id),
        "orgId": _normalize_uuid(org_id),
        "channel": request.channel,
    }

    if user_id:
        chat_data, chat_counts = _export_chat_data(session, user_id)
        payload["chat"] = chat_data
        counts.update(chat_counts)

        notebook_data, notebook_counts = _export_notebooks(session, user_id)
        payload["notebookData"] = notebook_data
        counts.update(notebook_counts)

        alerts = _export_alert_rules(session, user_id)
        payload["alertRules"] = alerts
        counts["alertRules"] = len(alerts)

        snapshots = _export_digest_snapshots(session, user_id, org_id)
        payload["digestSnapshots"] = snapshots
        counts["digestSnapshots"] = len(snapshots)

        audit_rows = _export_audit_rows(session, user_id)
        payload["auditTrail"] = audit_rows
        counts["auditTrail"] = len(audit_rows)

        lightmem = user_settings_service.read_user_lightmem_settings(user_id)
        payload["lightmemSettings"] = lightmem.settings.to_dict()

    return payload, counts


def _export_chat_data(session: Session, user_id: uuid.UUID) -> Tuple[Dict[str, Any], Dict[str, int]]:
    sessions = (
        session.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.asc())
        .all()
    )
    serialized_sessions: List[Dict[str, Any]] = []
    message_total = 0
    archive_total = 0
    for session_row in sessions:
        messages = (
            session.query(ChatMessage)
                .filter(ChatMessage.session_id == session_row.id)
                .order_by(ChatMessage.seq.asc())
                .all()
        )
        archives = (
            session.query(ChatMessageArchive)
                .filter(ChatMessageArchive.session_id == session_row.id)
                .order_by(ChatMessageArchive.seq.asc())
                .all()
        )
        serialized_sessions.append(
            {
                "id": str(session_row.id),
                "title": session_row.title,
                "summary": session_row.summary,
                "contextType": session_row.context_type,
                "contextId": session_row.context_id,
                "createdAt": _to_iso(session_row.created_at),
                "updatedAt": _to_iso(session_row.updated_at),
                "archivedAt": _to_iso(session_row.archived_at),
                "messages": [
                    {
                        "seq": message.seq,
                        "role": message.role,
                        "content": message.content,
                        "meta": message.meta,
                        "state": message.state,
                        "createdAt": _to_iso(message.created_at),
                    }
                    for message in messages
                ],
                "archived": [
                    {
                        "seq": archive.seq,
                        "payload": archive.payload,
                        "archivedAt": _to_iso(archive.archived_at),
                    }
                    for archive in archives
                ],
            }
        )
        message_total += len(messages)
        archive_total += len(archives)
    counts = {"chatSessions": len(serialized_sessions), "chatMessages": message_total, "chatArchive": archive_total}
    return {"sessions": serialized_sessions}, counts


def _export_notebooks(session: Session, user_id: uuid.UUID) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    entries = (
        session.query(NotebookEntry)
        .filter(NotebookEntry.author_id == user_id)
        .order_by(NotebookEntry.created_at.asc())
        .all()
    )
    serialized: List[Dict[str, Any]] = []
    notebook_ids: set[uuid.UUID] = set()
    for entry in entries:
        notebook_ids.add(entry.notebook_id)
        serialized.append(
            {
                "id": str(entry.id),
                "notebookId": str(entry.notebook_id),
                "highlight": entry.highlight,
                "annotation": entry.annotation,
                "annotationFormat": entry.annotation_format,
                "tags": entry.tags,
                "source": entry.source,
                "isPinned": entry.is_pinned,
                "position": entry.position,
                "createdAt": _to_iso(entry.created_at),
                "updatedAt": _to_iso(entry.updated_at),
            }
        )
    shares = (
        session.query(NotebookShare)
        .filter(NotebookShare.created_by == user_id)
        .order_by(NotebookShare.created_at.desc())
        .all()
    )
    serialized_shares = [
        {
            "id": str(share.id),
            "notebookId": str(share.notebook_id),
            "token": share.token,
            "expiresAt": _to_iso(share.expires_at),
            "revokedAt": _to_iso(share.revoked_at),
            "lastAccessedAt": _to_iso(share.last_accessed_at),
            "createdAt": _to_iso(share.created_at),
        }
        for share in shares
    ]

    notebooks = (
        session.query(Notebook).filter(Notebook.id.in_(list(notebook_ids))).all()
        if notebook_ids
        else []
    )
    notebook_map = {
        str(notebook.id): {
            "title": notebook.title,
            "summary": notebook.summary,
            "tags": notebook.tags,
            "createdAt": _to_iso(notebook.created_at),
        }
        for notebook in notebooks
    }
    entries_payload = [
        {
            **entry,
            "notebook": notebook_map.get(entry["notebookId"]),
        }
        for entry in serialized
    ]
    return (
        {
            "entries": entries_payload,
            "shares": serialized_shares,
        },
        {
            "notebookEntries": len(entries_payload),
            "notebookShares": len(serialized_shares),
        },
    )
            {
                **entry,
                "notebook": notebook_map.get(entry["notebookId"]),
            }
            for entry in serialized
        ],
        {
            "notebookEntries": len(serialized),
            "notebookShares": len(serialized_shares),
        },
    )


def _export_alert_rules(session: Session, user_id: uuid.UUID) -> List[Dict[str, Any]]:
    rules = (
        session.query(AlertRule)
        .filter(AlertRule.user_id == user_id)
        .order_by(AlertRule.created_at.asc())
        .all()
    )
    return [
        {
            "id": str(rule.id),
            "name": rule.name,
            "status": rule.status,
            "trigger": rule.trigger,
            "filters": rule.filters,
            "channels": rule.channels,
            "frequency": rule.frequency,
            "createdAt": _to_iso(rule.created_at),
            "updatedAt": _to_iso(rule.updated_at),
        }
        for rule in rules
    ]


def _export_digest_snapshots(
    session: Session,
    user_id: uuid.UUID,
    org_id: Optional[uuid.UUID],
) -> List[Dict[str, Any]]:
    query = session.query(DigestSnapshot).filter(DigestSnapshot.user_id == user_id)
    if org_id:
        query = query.filter(DigestSnapshot.org_id == org_id)
    snapshots = query.order_by(DigestSnapshot.digest_date.desc()).all()
    return [
        {
            "digestDate": snapshot.digest_date.isoformat(),
            "timeframe": snapshot.timeframe,
            "channel": snapshot.channel,
            "payload": snapshot.payload,
            "updatedAt": _to_iso(snapshot.updated_at),
        }
        for snapshot in snapshots
    ]


def _export_audit_rows(session: Session, user_id: uuid.UUID) -> List[Dict[str, Any]]:
    rows = (
        session.execute(
            text(
                """
                SELECT ts, action, source, target_id, feature_flags, extra
                FROM audit_logs
                WHERE user_id = :user_id
                ORDER BY ts DESC
                LIMIT :limit
                """
            ),
            {"user_id": str(user_id), "limit": AUDIT_EXPORT_LIMIT},
        )
        .mappings()
        .all()
    )
    return [
        {
            "ts": row["ts"].isoformat() if row.get("ts") else None,
            "action": row.get("action"),
            "source": row.get("source"),
            "targetId": row.get("target_id"),
            "featureFlags": row.get("feature_flags"),
            "extra": row.get("extra"),
        }
        for row in rows
    ]


def _run_deletion(session: Session, request: DSARRequest) -> Dict[str, Any]:
    user_id = request.user_id
    if user_id is None:
        return {"message": "user_id_missing"}
    stats = {
        "chatDeleted": _delete_chat_rows(session, user_id),
        "notebookEntriesDeleted": _delete_notebook_rows(session, user_id),
        "alertRulesDeleted": _execute_delete(
            session,
            "DELETE FROM alert_rules WHERE user_id = :user_id",
            {"user_id": str(user_id)},
        ),
        "digestSnapshotsDeleted": _execute_delete(
            session,
            "DELETE FROM digest_snapshots WHERE user_id = :user_id",
            {"user_id": str(user_id)},
        ),
        "notebookSharesDeleted": _execute_delete(
            session,
            "DELETE FROM notebook_shares WHERE created_by = :user_id",
            {"user_id": str(user_id)},
        ),
    }
    user_settings_service.delete_user_lightmem_settings(user_id)
    _redact_audit_entries(session, user_id)
    session.flush()
    return stats


def _delete_chat_rows(session: Session, user_id: uuid.UUID) -> Dict[str, int]:
    stats = {"sessions": 0, "messages": 0, "archives": 0}
    session_ids = [
        row[0]
        for row in session.execute(
            select(ChatSession.id).where(ChatSession.user_id == user_id)
        ).all()
    ]
    if session_ids:
        stats["messages"] = _execute_delete(
            session,
            "DELETE FROM chat_messages WHERE session_id = ANY(:session_ids)",
            {"session_ids": session_ids},
        )
        stats["archives"] = _execute_delete(
            session,
            "DELETE FROM chat_messages_archive WHERE session_id = ANY(:session_ids)",
            {"session_ids": session_ids},
        )
    stats["sessions"] = _execute_delete(
        session,
        "DELETE FROM chat_sessions WHERE user_id = :user_id",
        {"user_id": str(user_id)},
    )
    return stats


def _delete_notebook_rows(session: Session, user_id: uuid.UUID) -> int:
    rows = session.execute(
        text(
            """
            DELETE FROM notebook_entries
            WHERE author_id = :user_id
            RETURNING notebook_id
            """
        ),
        {"user_id": str(user_id)},
    ).fetchall()
    if not rows:
        return 0

    notebook_ids = {row[0] for row in rows if row[0]}
    for notebook_id in notebook_ids:
        remaining = session.execute(
            text("SELECT COUNT(*) FROM notebook_entries WHERE notebook_id = :notebook_id"),
            {"notebook_id": str(notebook_id)},
        ).scalar_one()
        session.execute(
            text(
                """
                UPDATE notebooks
                SET entry_count = :remaining,
                    last_activity_at = NOW()
                WHERE id = :notebook_id
                """
            ),
            {"notebook_id": str(notebook_id), "remaining": int(remaining or 0)},
        )
    return len(rows)


def _redact_audit_entries(session: Session, user_id: uuid.UUID) -> None:
    session.execute(
        text(
            """
            UPDATE audit_logs
            SET user_id = NULL,
                extra = COALESCE(extra, '{}'::jsonb) || jsonb_build_object('dsarRedacted', TRUE)
            WHERE user_id = :user_id
            """
        ),
        {"user_id": str(user_id)},
    )


def _execute_delete(session: Session, sql: str, params: Dict[str, Any]) -> int:
    result = session.execute(text(sql), params)
    return max(result.rowcount or 0, 0)


__all__ = [
    "DSARRequestRecord",
    "DSARServiceError",
    "create_request",
    "list_requests",
    "process_pending_requests",
]
