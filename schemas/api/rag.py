"""Pydantic schemas for the RAG API endpoints."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict, constr


class FilingFilter(BaseModel):
    """Lightweight metadata filters to narrow candidate filings."""

    sector: Optional[str] = Field(default=None, description="Filter by sector classification.")
    ticker: Optional[str] = Field(default=None, description="Filter by primary ticker symbol.")
    min_published_at: Optional[str] = Field(default=None, description="ISO timestamp lower bound.")
    max_published_at: Optional[str] = Field(default=None, description="ISO timestamp upper bound.")
    sentiment: Optional[str] = Field(default=None, description="Filter by sentiment label (positive/neutral/negative).")


class RAGQueryRequest(BaseModel):
    """Request payload for /rag/query."""

    question: constr(strip_whitespace=True, min_length=1)  # type: ignore[type-arg]
    filing_id: Optional[constr(strip_whitespace=True, min_length=1)] = Field(  # type: ignore[type-arg]
        default=None,
        description="Explicit filing focus. If omitted, the service will auto-select the most relevant filing.",
    )
    top_k: int = Field(4, ge=1, le=20, description="Maximum number of chunks per filing to retrieve from the vector store.")
    max_filings: int = Field(3, ge=1, le=10, description="Maximum number of filings to evaluate for a response.")
    run_self_check: bool = Field(True, description="Enqueue asynchronous self-check task.")
    filters: FilingFilter = Field(default_factory=FilingFilter, description="Optional metadata filters applied during retrieval.")
    session_id: Optional[uuid.UUID] = Field(default=None)
    turn_id: Optional[Union[str, uuid.UUID]] = Field(
        default=None,
        description="Client-provided turn identifier (UUID or string).",
    )
    user_message_id: Optional[uuid.UUID] = Field(default=None)
    assistant_message_id: Optional[uuid.UUID] = Field(default=None)
    retry_of_message_id: Optional[uuid.UUID] = Field(default=None)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    meta: Dict[str, Any] = Field(default_factory=dict)


class RelatedFiling(BaseModel):
    filing_id: str
    score: float = Field(..., description="Ranking score used during selection.")
    title: Optional[str] = Field(default=None)
    sentiment: Optional[str] = Field(default=None)
    published_at: Optional[str] = Field(default=None)


class RAGQueryResponse(BaseModel):
    """Response payload returned by /rag/query."""

    question: str
    filing_id: Optional[str] = None
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
    related_filings: List[RelatedFiling] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


__all__ = ["RAGQueryRequest", "RAGQueryResponse", "RelatedFiling", "FilingFilter"]
