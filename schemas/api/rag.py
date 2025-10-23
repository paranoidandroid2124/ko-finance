"""Pydantic schemas for the RAG API endpoints."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict, constr


class RAGQueryRequest(BaseModel):
    """Request payload for /rag/query."""

    question: constr(strip_whitespace=True, min_length=1)  # type: ignore[type-arg]
    filing_id: constr(strip_whitespace=True, min_length=1)  # type: ignore[type-arg]
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of chunks to retrieve from the vector store.")
    run_self_check: bool = Field(True, description="Enqueue asynchronous self-check task.")
    session_id: Optional[uuid.UUID] = Field(default=None)
    turn_id: Optional[uuid.UUID] = Field(default=None)
    user_message_id: Optional[uuid.UUID] = Field(default=None)
    assistant_message_id: Optional[uuid.UUID] = Field(default=None)
    retry_of_message_id: Optional[uuid.UUID] = Field(default=None)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    meta: Dict[str, Any] = Field(default_factory=dict)


class RAGQueryResponse(BaseModel):
    """Response payload returned by /rag/query."""

    question: str
    filing_id: str
    session_id: Optional[uuid.UUID] = None
    turn_id: Optional[uuid.UUID] = None
    user_message_id: Optional[uuid.UUID] = None
    assistant_message_id: Optional[uuid.UUID] = None
    answer: str
    context: List[Dict[str, Any]] = Field(default_factory=list)
    citations: Dict[str, List[str]] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    highlights: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    original_answer: Optional[str] = None
    model_used: Optional[str] = None
    trace_id: Optional[str] = None
    judge_decision: Optional[str] = Field(default=None, description="Result from regulatory judge model.")
    judge_reason: Optional[str] = Field(default=None, description="Explanation from judge model.")
    meta: Dict[str, Any] = Field(default_factory=dict)
    state: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


__all__ = ["RAGQueryRequest", "RAGQueryResponse"]
