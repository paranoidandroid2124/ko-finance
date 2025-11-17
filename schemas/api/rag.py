"""Pydantic schemas for the RAG API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator
from schemas.api.rag_v2 import (
    EvidenceSchema as EvidenceSchemaV2,
    RagGridCellResponse as RagGridCellResponseV2,
    RagGridRequest as RagGridRequestV2,
    RagGridResponse as RagGridResponseV2,
    RagQueryFiltersSchema as RagQueryFiltersSchemaV2,
    RagQueryRequest as RagQueryRequestV2,
    RagQueryResponse as RagQueryResponseV2,
    RagWarningSchema as RagWarningSchemaV2,
)


class FilingFilter(BaseModel):
    """Lightweight metadata filters to narrow candidate filings."""

    sector: Optional[str] = Field(default=None, description="Filter by sector classification.")
    ticker: Optional[str] = Field(default=None, description="Filter by primary ticker symbol.")
    min_published_at: Optional[str] = Field(default=None, description="ISO timestamp lower bound.")
    max_published_at: Optional[str] = Field(default=None, description="ISO timestamp upper bound.")
    sentiment: Optional[str] = Field(default=None, description="Filter by sentiment label (positive/neutral/negative).")


class RAGQueryRequest(BaseModel):
    """Request payload for /rag/query."""

    question: str = Field(
        ...,
        min_length=1,
        description="Fully formed analyst question passed to the RAG pipeline.",
    )
    filing_id: Optional[str] = Field(
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

    @field_validator("question", mode="before")
    def _normalize_question(cls, value: Any) -> str:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("question must not be empty")
            return stripped
        raise TypeError("question must be a string")

    @field_validator("filing_id", mode="before")
    def _normalize_filing_id(cls, value: Optional[Any]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return str(value)


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


class CitationEvidence(BaseModel):
    """Structured citation metadata used to render evidence snippets."""

    label: str = Field(..., description="Display label rendered next to the citation (e.g., '(p.5)').")
    bucket: Optional[Literal["page", "table", "footnote"]] = Field(
        default=None,
        description="Citation bucket derived from the source chunk type.",
    )
    chunk_id: Optional[str] = Field(default=None, description="Underlying chunk identifier.")
    page_number: Optional[int] = Field(default=None, ge=1, description="Page number where the snippet originates.")
    char_start: Optional[int] = Field(
        default=None,
        ge=0,
        description="Character offset (inclusive) relative to the source page/text.",
    )
    char_end: Optional[int] = Field(
        default=None,
        ge=0,
        description="Character offset (exclusive) relative to the source page/text.",
    )
    sentence_hash: Optional[str] = Field(
        default=None,
        description="Normalized hash of the quoted sentence used for drift detection.",
    )
    document_id: Optional[str] = Field(default=None, description="Identifier of the document/filing.")
    document_url: Optional[str] = Field(default=None, description="Base URL for the source document.")
    deeplink_url: Optional[str] = Field(default=None, description="Deep link that opens the highlight in the viewer.")
    source: Optional[str] = Field(default=None, description="Origin tag of the chunk (pdf/xml/ocr...).")
    excerpt: Optional[str] = Field(default=None, description="Quote snippet tied to the citation.")
    anchor: Optional[EvidenceAnchor] = Field(default=None, description="Anchor metadata reused for highlights.")

    model_config = ConfigDict(from_attributes=True)


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
    diff_type: Optional[Literal["created", "updated", "unchanged", "removed"]] = Field(
        default=None,
        description="Diff classification compared to previously stored snapshot.",
    )
    previous_quote: Optional[str] = Field(
        default=None,
        description="Quote value from the previous snapshot, if any.",
    )
    previous_section: Optional[str] = Field(
        default=None,
        description="Section label from the previous snapshot.",
    )
    previous_page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="Page number from the previous snapshot.",
    )
    previous_anchor: Optional[EvidenceAnchor] = Field(
        default=None,
        description="Anchor metadata from the previous snapshot.",
    )
    previous_source_reliability: Optional[Literal["high", "medium", "low"]] = Field(
        default=None,
        description="Reliability tier from the previous snapshot.",
    )
    previous_self_check: Optional[SelfCheckResult] = Field(
        default=None,
        description="Self-check verdict attached to the previous snapshot.",
    )
    diff_changed_fields: Optional[List[str]] = Field(
        default=None,
        description="Fields that changed compared to the previous snapshot.",
    )
    filing_id: Optional[str] = Field(default=None, description="Underlying filing identifier.")
    receipt_no: Optional[str] = Field(default=None, description="DART receipt number, if available.")
    document_title: Optional[str] = Field(default=None, description="Document title associated with the evidence.")
    document_url: Optional[str] = Field(default=None, description="Primary document URL.")
    viewer_url: Optional[str] = Field(default=None, description="Viewer URL for inline PDF rendering.")
    download_url: Optional[str] = Field(default=None, description="Direct download URL for the document.")
    document: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured document metadata payload.",
    )
    table_reference: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured table metadata payload (if evidence is derived from a table).",
    )

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
    citations: Dict[str, List[Union[str, CitationEvidence]]] = Field(default_factory=dict)
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
    rag_mode: Optional[Literal["vector", "optional", "none"]] = Field(
        default=None,
        description="Selected retrieval strategy for this answer.",
    )

    model_config = ConfigDict(from_attributes=True)


class RAGDeeplinkPayload(BaseModel):
    """Payload returned when resolving a deeplink token."""

    token: str = Field(..., description="Opaque deeplink token used for auditing.")
    document_url: str = Field(..., description="Underlying PDF/HTML document URL.")
    page_number: int = Field(..., ge=1, description="Page number to focus in the viewer.")
    char_start: Optional[int] = Field(
        default=None, ge=0, description="Inclusive character offset relative to the page content."
    )
    char_end: Optional[int] = Field(
        default=None, ge=0, description="Exclusive character offset relative to the page content."
    )
    sentence_hash: Optional[str] = Field(default=None, description="Hash of the quoted sentence.")
    chunk_id: Optional[str] = Field(default=None, description="Chunk identifier associated with the citation.")
    document_id: Optional[str] = Field(default=None, description="Internal document identifier (e.g., filing ID).")
    excerpt: Optional[str] = Field(default=None, description="Optional snippet attached to the deeplink.")
    expires_at: datetime = Field(..., description="Timestamp indicating when the token expires.")

    model_config = ConfigDict(from_attributes=True)


class RAGTelemetryEvent(BaseModel):
    """Client-side telemetry event emitted from the dashboard."""

    name: Literal[
        "rag.deeplink_opened",
        "rag.deeplink_failed",
        "rag.deeplink_viewer_ready",
        "rag.deeplink_viewer_error",
        "rag.deeplink_viewer_original_opened",
        "rag.deeplink_viewer_original_failed",
        "rag.evidence_view",
        "rag.evidence_diff_toggle",
    ]
    source: Optional[str] = Field(default=None, description="Logical source of the event (e.g., 'chat', 'viewer').")
    timestamp: Optional[datetime] = Field(default=None, description="Client-side timestamp for the event.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the event.")


class RAGTelemetryRequest(BaseModel):
    """Telemetry payload posted from the dashboard."""

    events: List[RAGTelemetryEvent] = Field(..., min_length=1, max_length=50)


class RAGTelemetryResponse(BaseModel):
    """Result of ingesting telemetry events."""

    accepted: int = Field(..., ge=0, description="Number of events accepted for processing.")


EvidenceSchema = EvidenceSchemaV2
RagGridRequest = RagGridRequestV2
RagGridResponse = RagGridResponseV2
RagGridCellResponse = RagGridCellResponseV2
RagQueryFiltersSchema = RagQueryFiltersSchemaV2
RagQueryRequest = RagQueryRequestV2
RagQueryResponse = RagQueryResponseV2
RagWarningSchema = RagWarningSchemaV2


__all__ = [
    "CitationEvidence",
    "EvidenceAnchor",
    "FilingFilter",
    "PDFRect",
    "EvidenceSchema",
    "RAGEvidence",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "RAGDeeplinkPayload",
    "RAGTelemetryEvent",
    "RAGTelemetryRequest",
    "RAGTelemetryResponse",
    "RelatedFiling",
    "SelfCheckResult",
    "EvidenceSchema",
    "RagGridRequest",
    "RagGridResponse",
    "RagGridCellResponse",
    "RagQueryFiltersSchema",
    "RagQueryRequest",
    "RagQueryResponse",
    "RagWarningSchema",
]
