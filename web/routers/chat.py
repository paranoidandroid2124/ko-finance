"""FastAPI routes for chat session persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models.chat import ChatMessage, ChatSession
from schemas.api.chat import (
    ChatMessageCreateRequest,
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatMessageStateUpdateRequest,
    ChatSessionCreateRequest,
    ChatSessionListResponse,
    ChatSessionRenameRequest,
    ChatSessionResponse,
)
from services import chat_service
from services.plan_service import PlanContext
from web.deps import get_plan_context
from web.quota_guard import enforce_quota

router = APIRouter(prefix="/chat", tags=["Chat"])


def _parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format.") from exc


def _parse_cursor(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor value.") from exc


def _coerce_uuid(value: Optional[Union[str, uuid.UUID]]) -> uuid.UUID:
    """Convert arbitrary identifiers into deterministic UUIDs."""
    if isinstance(value, uuid.UUID):
        return value
    if value:
        text = str(value)
        try:
            return uuid.UUID(text)
        except ValueError:
            return uuid.uuid5(uuid.NAMESPACE_URL, text)
    return uuid.uuid4()


def _guard_session_owner(session, user_id: Optional[uuid.UUID], org_id: Optional[uuid.UUID]) -> None:
    if session.user_id and user_id and session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden session access.")
    if session.org_id and org_id and session.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden session access.")


@router.get("/sessions", response_model=ChatSessionListResponse)
def list_sessions(
    limit: int = Query(20, ge=1, le=50),
    cursor: Optional[str] = Query(None),
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ChatSessionListResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    after = _parse_cursor(cursor)
    sessions = chat_service.list_chat_sessions(db, user_id=user_id, org_id=org_id, limit=limit, after=after)
    next_cursor = None
    if sessions and len(sessions) == limit:
        next_cursor = sessions[-1].updated_at.isoformat()
    return ChatSessionListResponse(sessions=sessions, next_cursor=next_cursor)


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatSessionCreateRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    try:
        session = chat_service.create_chat_session(
            db,
            user_id=user_id,
            org_id=org_id,
            title=payload.title,
            context_type=payload.context_type,
            context_id=payload.context_id,
            token_budget=payload.token_budget,
        )
        db.commit()
        db.refresh(session)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return session


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
def rename_session(
    session_id: uuid.UUID,
    payload: ChatSessionRenameRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    _guard_session_owner(session, user_id, org_id)
    try:
        renamed = chat_service.rename_chat_session(
            db,
            session_id=session_id,
            title=payload.title,
            expected_version=payload.version,
        )
        db.commit()
        db.refresh(renamed)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return renamed


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: uuid.UUID,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None:
        return
    _guard_session_owner(session, user_id, org_id)
    chat_service.archive_chat_session(db, session_id=session_id)
    db.commit()


@router.delete("/sessions", response_model=dict)
def delete_all_sessions(
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    count = chat_service.clear_chat_sessions(db, user_id=user_id, org_id=org_id)
    db.commit()
    return {"archived": count}


@router.get("/messages", response_model=ChatMessageListResponse)
def list_messages(
    session_id: uuid.UUID,
    after_seq: Optional[int] = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=200),
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ChatMessageListResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    _guard_session_owner(session, user_id, org_id)
    query = db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
    if after_seq is not None:
        query = query.filter(ChatMessage.seq > after_seq)
    query = query.order_by(ChatMessage.seq.asc()).limit(limit)
    messages = query.all()
    next_seq = None
    if messages and len(messages) == limit:
        next_seq = messages[-1].seq
    return ChatMessageListResponse(messages=messages, next_seq=next_seq)


@router.post("/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
def create_message(
    payload: ChatMessageCreateRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    idempotency_key_header: Optional[str] = Header(default=None, convert_underscores=False, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(get_plan_context),
) -> ChatMessageResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    session = db.query(ChatSession).filter(ChatSession.id == payload.session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    _guard_session_owner(session, user_id, org_id)
    enforce_quota("api.chat", plan=plan, user_id=user_id, org_id=org_id)
    idempotency_key = payload.idempotency_key or idempotency_key_header
    turn_id = _coerce_uuid(payload.turn_id)
    try:
        message = chat_service.create_chat_message(
            db,
            session_id=payload.session_id,
            role=payload.role,
            content=payload.content,
            turn_id=turn_id,
            idempotency_key=idempotency_key,
            reply_to_message_id=payload.reply_to_message_id,
            retry_of_message_id=payload.retry_of_message_id,
            meta=payload.meta,
            state=payload.state,
        )
        db.commit()
        db.refresh(message)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return message


@router.patch("/messages/{message_id}", response_model=ChatMessageResponse)
def update_message(
    message_id: uuid.UUID,
    payload: ChatMessageStateUpdateRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    session = db.query(ChatSession).filter(ChatSession.id == message.session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    _guard_session_owner(session, user_id, org_id)
    try:
        updated = chat_service.update_message_state(
            db,
            message_id=message_id,
            state=payload.state,
            error_code=payload.error_code,
            error_message=payload.error_message,
            content=payload.content,
            meta=payload.meta,
        )
        needs_summary = updated.role == "assistant" and payload.state == "ready" and chat_service.should_trigger_summary(
            db, session
        )
        db.commit()
        db.refresh(updated)
        if needs_summary:
            chat_service.enqueue_session_summary(session.id)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return updated
