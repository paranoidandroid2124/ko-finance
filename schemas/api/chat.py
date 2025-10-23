"""Pydantic schemas for chat session APIs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict


class ChatSessionCreateRequest(BaseModel):
    title: Optional[str] = None
    context_type: Optional[str] = Field(default=None, max_length=64)
    context_id: Optional[str] = Field(default=None, max_length=128)
    token_budget: Optional[int] = Field(default=None, ge=0)


class ChatSessionRenameRequest(BaseModel):
    title: str
    version: Optional[int] = None


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    summary: Optional[str] = None
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    message_count: int
    token_budget: Optional[int] = None
    summary_tokens: Optional[int] = None
    memory_snapshot: Optional[Dict[str, Any]] = None
    last_message_at: Optional[datetime] = None
    last_read_at: Optional[datetime] = None
    version: int
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSessionResponse]
    next_cursor: Optional[str] = None


class ChatMessageCreateRequest(BaseModel):
    session_id: uuid.UUID
    role: str
    content: Optional[str] = None
    turn_id: Optional[Union[str, uuid.UUID]] = Field(
        default=None,
        description="Client-provided turn identifier (accepts UUID or arbitrary string).",
    )
    reply_to_message_id: Optional[uuid.UUID] = None
    retry_of_message_id: Optional[uuid.UUID] = None
    state: str = Field(default="pending")
    meta: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class ChatMessageStateUpdateRequest(BaseModel):
    state: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    content: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    seq: int
    turn_id: uuid.UUID
    retry_of_message_id: Optional[uuid.UUID] = None
    reply_to_message_id: Optional[uuid.UUID] = None
    role: str
    state: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    content: Optional[str] = None
    meta: Dict[str, Any]
    idempotency_key: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageListResponse(BaseModel):
    messages: List[ChatMessageResponse]
    next_seq: Optional[int] = None
