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
from models.chat import ChatMessage, ChatMessageArchive, ChatSession
from models.dsar import DSARRequest
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


def _artifact_dir_for_request(request: DSARRequest) -> Path:
    """Build export directory as DSAR_EXPORT_DIR/{owner}/{request_id}/."""
    if request.user_id:
        owner_segment = str(request.user_id)
    elif request.org_id:
        owner_segment = f"org_{request.org_id}"
    else:
        owner_segment = "anonymous"
    destination = DSAR_EXPORT_ROOT / owner_segment / str(request.id)
    destination.mkdir(parents=True, exist_ok=True)
    return destination


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
    artifact_dir = _artifact_dir_for_request(request)
    artifact = artifact_dir / "export.json"
    artifact.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    size_bytes = artifact.stat().st_size if artifact.exists() else 0
    meta = {
        "resourceCounts": counts,
        "artifactBytes": size_bytes,
        "artifactPath": str(artifact),
        "artifactDir": str(artifact_dir),
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

        audit_rows = _export_audit_rows(session, user_id)
        payload["auditTrail"] = audit_rows
        counts["auditTrail"] = len(audit_rows)

        lightmem = user_settings_service.read_user_lightmem_settings(user_id)
        payload["lightmemSettings"] = lightmem.settings.to_dict()
        payload["lightmemSettingsMeta"] = {
            "updatedAt": _to_iso(lightmem.updated_at),
            "updatedBy": lightmem.updated_by,
        }
        counts["userLightmemSettings"] = 1

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
    counts = {
        "chatSessions": len(serialized_sessions),
        "chatMessages": message_total,
        "chatArchive": archive_total,
    }
    return {"sessions": serialized_sessions}, counts


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
    deleted_rows: Dict[str, int] = {}
    chat_deleted = _delete_chat_rows(session, user_id)
    deleted_rows["chat_sessions"] = chat_deleted["sessions"]
    deleted_rows["chat_messages"] = chat_deleted["messages"]
    deleted_rows["chat_messages_archive"] = chat_deleted["archives"]

    lightmem_removed = user_settings_service.delete_user_lightmem_settings(user_id)
    deleted_rows["user_lightmem_settings"] = 1 if lightmem_removed else 0

    audit_redacted = _redact_audit_entries(session, user_id)
    deleted_rows["audit_logs_redacted"] = audit_redacted

    session.flush()
    return {"deletedRows": deleted_rows}


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


def _redact_audit_entries(session: Session, user_id: uuid.UUID) -> int:
    result = session.execute(
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
    return max(result.rowcount or 0, 0)


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
