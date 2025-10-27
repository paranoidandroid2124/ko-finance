"""Pydantic schemas for the RAG API endpoints."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Union, Literal

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


class PDFRect(BaseModel):
    """Rectangle coordinates for PDF highlight regions."""

    page: int = Field(..., ge=1, description="1-based page index.")
    x: float = Field(..., ge=0)
    y: float = Field(..., ge=0)
    width: float = Field(..., ge=0)
    height: float = Field(..., ge=0)


class EvidenceAnchor(BaseModel):
    """Information required to map an evidence chunk back to the PDF."""

    paragraph_id: Optional[str] = Field(default=None, description="Stable identifier for the paragraph within the document.")
    pdf_rect: Optional[PDFRect] = Field(default=None, description="Bounding box for PDF highlight rendering.")
    similarity: Optional[float] = Field(default=None, ge=0, le=1, description="Cosine similarity between query and chunk.")


class SelfCheckResult(BaseModel):
    """Self-check verdict emitted by the judge model."""

    score: Optional[float] = Field(default=None, ge=0, le=1, description="Normalised 0-1 confidence.")
    verdict: Optional[Literal["pass", "warn", "fail"]] = Field(default=None, description="Qualitative verdict for the evidence.")
    explanation: Optional[str] = Field(default=None, description="Optional explanation for UI tooltips.")


class RAGEvidence(BaseModel):
    """Structured evidence chunk returned alongside the answer."""

    urn_id: str = Field(..., description="Unique identifier for the evidence unit.")
    chunk_id: Optional[str] = Field(default=None, description="Underlying vector store chunk identifier.")
    page_number: Optional[int] = Field(default=None, ge=1, description="1-based PDF page index.")
    section: Optional[str] = Field(default=None, description="Heading or logical section where the quote was found.")
    quote: str = Field(..., description="Excerpt from the source document supporting the answer.")
    content: Optional[str] = Field(
        default=None,
        description="Deprecated: maintained for backwards compatibility. Mirrors `quote`.",
    )
    anchor: Optional[EvidenceAnchor] = Field(default=None, description="Anchor metadata for highlights.")
    self_check: Optional[SelfCheckResult] = Field(default=None, description="Self-check information for the evidence.")
    source_reliability: Optional[Literal["high", "medium", "low"]] = Field(
        default=None,
        description="Reliability tier for the underlying source.",
    )
    created_at: Optional[str] = Field(default=None, description="ISO timestamp for diff snapshot ordering.")

    model_config = ConfigDict(from_attributes=True)


class RAGQueryResponse(BaseModel):
    """Response payload returned by /rag/query."""

    question: str
    filing_id: Optional[str] = None
    session_id: Optional[uuid.UUID] = None
    turn_id: Optional[uuid.UUID] = None
    user_message_id: Optional[uuid.UUID] = None
    assistant_message_id: Optional[uuid.UUID] = None
    answer: str
    context: List[RAGEvidence] = Field(default_factory=list)
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


__all__ = [
    "EvidenceAnchor",
    "FilingFilter",
    "PDFRect",
    "RAGEvidence",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "RelatedFiling",
    "SelfCheckResult",
]
