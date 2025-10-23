"""Persistence helpers for chat sessions and messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from core.env import env_int
from models.chat import ChatAudit, ChatMessage, ChatMessageArchive, ChatSession
from parse.celery_app import app

DEFAULT_SESSION_TITLE = "새 대화"
REQUIRED_META_KEYS = {
    "model": None,
    "prompt_version": None,
    "latency_ms": None,
    "input_tokens": None,
    "output_tokens": None,
    "cost": None,
    "retrieval": {"doc_ids": [], "hit_at_k": None},
    "guardrail": {"decision": None, "reason": None},
    "citations": {"page": [], "table": [], "footnote": []},
    "answer_preview": None,
    "conversation_summary": None,
    "recent_turn_count": None,
}

SUMMARY_TRIGGER_MESSAGES = env_int("CHAT_SUMMARY_TRIGGER_MESSAGES", 20, minimum=6)
RECENT_TURN_LIMIT = env_int("CHAT_MEMORY_RECENT_TURNS", 3, minimum=1)
SUMMARY_PREVIEW_LIMIT = env_int("CHAT_SUMMARY_PREVIEW_CHARS", 280, minimum=80)


def trim_preview(text: Optional[str]) -> str:
    if not text:
        return ""
    normalized = " ".join(text.split())
    if len(normalized) <= SUMMARY_PREVIEW_LIMIT:
        return normalized
    slice_length = max(0, SUMMARY_PREVIEW_LIMIT - 3)
    return normalized[:slice_length].rstrip() + "..."


def _collect_recent_messages(db: Session, session_id: uuid.UUID, limit_pairs: int) -> List[ChatMessage]:
    limit = max(1, limit_pairs) * 2
    recent = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.seq.desc())
        .limit(limit)
        .all()
    )
    recent.reverse()
    return recent


def build_conversation_memory(
    db: Session,
    session: ChatSession,
    *,
    recent_turn_limit: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    snapshot = session.memory_snapshot or {}
    recent_messages = _collect_recent_messages(
        db,
        session.id,
        recent_turn_limit or RECENT_TURN_LIMIT,
    )
    memory_turns: List[Dict[str, Any]] = []
    for message in recent_messages:
        if not message.content:
            continue
        turn_entry: Dict[str, Any] = {"role": message.role, "content": message.content}
        if message.role == "assistant" and isinstance(message.meta, dict):
            citations = message.meta.get("citations")
            if citations:
                turn_entry["citations"] = citations
        memory_turns.append(turn_entry)
    summary_text = snapshot.get("summary")
    citations = snapshot.get("citations") or []
    if not memory_turns and not summary_text:
        return None
    return {
        "summary": summary_text,
        "citations": citations,
        "recent_turns": memory_turns,
    }


def should_trigger_summary(db: Session, session: ChatSession, *, trigger_messages: Optional[int] = None) -> bool:
    threshold = trigger_messages or SUMMARY_TRIGGER_MESSAGES
    if threshold <= 0:
        return False
    snapshot = session.memory_snapshot or {}
    summarized_until = int(snapshot.get("summarized_until") or 0)
    unsummarized_count = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id, ChatMessage.seq > summarized_until)
        .count()
    )
    return unsummarized_count >= threshold and unsummarized_count > RECENT_TURN_LIMIT * 2


def enqueue_session_summary(session_id: uuid.UUID) -> None:
    try:
        app.send_task("m5.summarize_chat_session", args=[str(session_id)])
    except Exception:
        # Celery may be unavailable during some test runs; skip scheduling in that case.
        pass


def _ensure_meta_fields(meta: Optional[dict]) -> dict:
    prepared = dict(meta or {})
    for key, default_value in REQUIRED_META_KEYS.items():
        if key not in prepared:
            prepared[key] = default_value
    return prepared


def create_chat_session(
    db: Session,
    *,
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
    title: Optional[str] = None,
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    token_budget: Optional[int] = None,
) -> ChatSession:
    session = ChatSession(
        user_id=user_id,
        org_id=org_id,
        title=title.strip() if title and title.strip() else DEFAULT_SESSION_TITLE,
        context_type=context_type,
        context_id=context_id,
        token_budget=token_budget,
        message_count=0,
        last_message_at=None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()
    _insert_audit_row(db, session_id=session.id, action="session_created")
    return session


def list_chat_sessions(
    db: Session,
    *,
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
    limit: int = 20,
    after: Optional[datetime] = None,
) -> Iterable[ChatSession]:
    query = db.query(ChatSession).filter(ChatSession.archived_at.is_(None))
    if user_id:
        query = query.filter(ChatSession.user_id == user_id)
    if org_id:
        query = query.filter(ChatSession.org_id == org_id)
    if after:
        query = query.filter(ChatSession.updated_at < after)
    query = query.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc()).limit(limit)
    return query.all()


def rename_chat_session(
    db: Session,
    *,
    session_id: uuid.UUID,
    title: str,
    expected_version: Optional[int] = None,
) -> ChatSession:
    sanitized = title.strip() or DEFAULT_SESSION_TITLE
    query = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.archived_at.is_(None))
    if expected_version is not None:
        query = query.filter(ChatSession.version == expected_version)
    session = query.first()
    if session is None:
        raise ValueError("Session not found or version mismatch.")
    session.title = sanitized
    session.version += 1
    session.updated_at = datetime.now(timezone.utc)
    db.flush()
    _insert_audit_row(db, session_id=session.id, action="session_renamed", metadata={"title": sanitized})
    return session


def archive_chat_session(db: Session, *, session_id: uuid.UUID) -> None:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.archived_at.is_(None))
        .with_for_update()
        .first()
    )
    if session is None:
        return
    session.archived_at = datetime.now(timezone.utc)
    session.updated_at = session.archived_at
    db.flush()
    _insert_audit_row(db, session_id=session.id, action="session_archived")


def clear_chat_sessions(
    db: Session,
    *,
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
) -> int:
    query = db.query(ChatSession).filter(ChatSession.archived_at.is_(None))
    if user_id:
        query = query.filter(ChatSession.user_id == user_id)
    if org_id:
        query = query.filter(ChatSession.org_id == org_id)
    session_ids = [row.id for row in query.with_for_update().all()]
    now = datetime.now(timezone.utc)
    updated = (
        db.query(ChatSession)
        .filter(ChatSession.id.in_(session_ids))
        .update({ChatSession.archived_at: now, ChatSession.updated_at: now}, synchronize_session=False)
    )
    if session_ids:
        _insert_audit_row(
            db,
            session_id=None,
            action="session_bulk_archive",
            metadata={"count": len(session_ids)},
        )
    return updated or 0


def _next_sequence(db: Session, session_id: uuid.UUID) -> int:
    result = (
        db.query(ChatMessage.seq)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.seq.desc())
        .with_for_update()
        .first()
    )
    if result is None:
        return 0
    return int(result[0]) + 1


def create_chat_message(
    db: Session,
    *,
    message_id: Optional[uuid.UUID] = None,
    session_id: uuid.UUID,
    role: str,
    content: Optional[str],
    turn_id: uuid.UUID,
    idempotency_key: Optional[str],
    reply_to_message_id: Optional[uuid.UUID] = None,
    retry_of_message_id: Optional[uuid.UUID] = None,
    meta: Optional[dict] = None,
    state: str = "pending",
) -> ChatMessage:
    if idempotency_key:
        existing = (
            db.query(ChatMessage)
            .filter(ChatMessage.idempotency_key == idempotency_key)
            .with_for_update(read=True)
            .first()
        )
        if existing:
            return existing

    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.archived_at.is_(None)).with_for_update().first()
    if session is None:
        raise ValueError("Session not found or archived.")

    seq_value = _next_sequence(db, session_id)
    message = ChatMessage(
        id=message_id or uuid.uuid4(),
        session_id=session_id,
        seq=seq_value,
        turn_id=turn_id,
        retry_of_message_id=retry_of_message_id,
        reply_to_message_id=reply_to_message_id,
        role=role,
        content=content,
        state=state,
        idempotency_key=idempotency_key,
        meta=_ensure_meta_fields(meta),
        created_at=datetime.now(timezone.utc),
    )

    db.add(message)
    session.message_count += 1
    session.last_message_at = message.created_at
    session.updated_at = message.created_at
    db.flush()
    _insert_audit_row(
        db,
        session_id=session_id,
        message_id=message.id,
        action="message_created",
        metadata={"role": role, "seq": seq_value},
    )
    return message


def update_message_state(
    db: Session,
    *,
    message_id: uuid.UUID,
    state: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    content: Optional[str] = None,
    meta: Optional[dict] = None,
) -> ChatMessage:
    message = db.query(ChatMessage).filter(ChatMessage.id == message_id).with_for_update().first()
    if message is None:
        raise ValueError("Message not found.")
    message.state = state
    if error_code:
        message.error_code = error_code
    if error_message:
        message.error_message = error_message
    if content is not None:
        message.content = content
    if meta:
        current_meta = dict(message.meta or {})
        current_meta.update(_ensure_meta_fields(meta))
        message.meta = current_meta
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == message.session_id)
        .with_for_update()
        .first()
    )
    if session:
        session.last_message_at = max(session.last_message_at or message.created_at, message.created_at)
        session.updated_at = datetime.now(timezone.utc)
        if message.role == "assistant" and state == "ready":
            preview = trim_preview(message.content)
            if preview:
                session.summary = preview
            session.last_read_at = datetime.now(timezone.utc)
            if isinstance(message.meta, dict):
                snapshot = dict(session.memory_snapshot or {})
                citations = message.meta.get("citations")
                if citations:
                    snapshot["last_answer_citations"] = citations
                session.memory_snapshot = snapshot or session.memory_snapshot
    db.flush()
    _insert_audit_row(
        db,
        session_id=message.session_id,
        message_id=message.id,
        action="message_updated",
        metadata={"state": state, "error_code": error_code},
    )
    return message


def archive_chat_messages(
    db: Session,
    *,
    session_id: uuid.UUID,
    seq_threshold: int,
) -> int:
    candidates = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id, ChatMessage.seq <= seq_threshold)
        .order_by(ChatMessage.seq.asc())
        .all()
    )
    if not candidates:
        return 0
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id)
        .with_for_update()
        .first()
    )
    for message in candidates:
        archive_row = ChatMessageArchive(
            id=message.id,
            session_id=session_id,
            seq=message.seq,
            payload={
                "role": message.role,
                "content": message.content,
                "meta": message.meta,
                "state": message.state,
                "error_code": message.error_code,
                "error_message": message.error_message,
                "created_at": message.created_at.isoformat() if message.created_at else None,
            },
        )
        db.add(archive_row)
        db.delete(message)
    if session:
        session.message_count = max(0, session.message_count - len(candidates))
        session.updated_at = datetime.now(timezone.utc)
    db.flush()
    _insert_audit_row(
        db,
        session_id=session_id,
        action="message_archived",
        metadata={"count": len(candidates), "seq_threshold": seq_threshold},
    )
    return len(candidates)


def _insert_audit_row(
    db: Session,
    *,
    action: str,
    session_id: Optional[uuid.UUID] = None,
    message_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None,
) -> None:
    audit_row = ChatAudit(
        action=action,
        session_id=session_id,
        message_id=message_id,
        details=metadata,
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit_row)
