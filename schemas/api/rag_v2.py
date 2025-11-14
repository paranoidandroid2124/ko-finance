"""Pydantic schemas for the next-gen RAG endpoints (evidence-first + grid)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

EvidenceSourceType = Literal["filing", "news", "sector", "event", "portfolio", "memo"]


class EvidenceDiffSchema(BaseModel):
    type: Optional[str] = Field(
        default=None,
        description="Type of change detected (e.g. created, updated, removed).",
    )
    previous_reference: Optional[str] = Field(
        default=None,
        description="Identifier or URL pointing to the previous version.",
    )
    changed_fields: List[str] = Field(
        default_factory=list,
        description="Structured list of fields that changed across versions.",
    )
    delta_text: Optional[str] = Field(
        default=None,
        description="Short summary describing what changed.",
    )


class EvidenceSelfCheckSchema(BaseModel):
    verdict: Literal["pass", "fail", "warn", "unknown"] = "unknown"
    rationale: Optional[str] = Field(
        default=None,
        description="Rationale supplied by the judge/self-check model.",
    )
    hallucination_risk: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Probability estimate that the snippet contains hallucinations.",
    )


class EvidenceSchema(BaseModel):
    sourceType: EvidenceSourceType = Field(..., description="Data source type.")
    sourceId: Optional[str] = Field(default=None, description="Unique identifier for the source row/document.")
    sourceSlug: Optional[str] = Field(default=None, description="Human friendly slug for the source.")
    title: Optional[str] = Field(default=None, description="Headline/title of the evidence chunk.")
    publisher: Optional[str] = Field(default=None, description="Publisher or company issuing the document.")
    ticker: Optional[str] = Field(default=None, description="Primary security ticker associated with the evidence.")
    sector: Optional[str] = Field(default=None, description="KSIC/sector label tied to the source.")
    sentiments: List[str] = Field(default_factory=list, description="Optional sentiment tags.")
    publishedAt: Optional[str] = Field(default=None, description="ISO timestamp when the source was published.")
    section: Optional[str] = Field(default=None, description="Section title or logical grouping inside the document.")
    pageNumber: Optional[int] = Field(default=None, description="Page number for PDF-like sources.")
    anchors: List[str] = Field(default_factory=list, description="Anchor identifiers (paragraph, table, clause).")
    content: str = Field(..., description="Raw text snippet returned to the LLM.")
    summary: Optional[str] = Field(default=None, description="Optional pre-computed summary of the snippet.")
    score: Optional[float] = Field(default=None, description="Combined relevance score after ranking.")
    rerankScore: Optional[float] = Field(default=None, description="Score returned by the reranker (if any).")
    confidence: Optional[float] = Field(default=None, description="LLM confidence between 0 and 1.")
    diff: Optional[EvidenceDiffSchema] = Field(default=None, description="Diff metadata when comparing versions.")
    selfCheck: Optional[EvidenceSelfCheckSchema] = Field(default=None, description="Guardrail/self-check output.")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Catch-all metadata bag.")
    viewerUrl: Optional[str] = Field(default=None, description="URL to the inline viewer.")
    downloadUrl: Optional[str] = Field(default=None, description="URL to download the original document.")

    @field_validator("sentiments")
    @classmethod
    def _unique_tags(cls, value: List[str]) -> List[str]:
        seen: set[str] = set()
        unique: List[str] = []
        for tag in value:
            normalized = str(tag).strip()
            if not normalized or normalized in seen:
                continue
            unique.append(normalized)
            seen.add(normalized)
        return unique


class RagQueryFiltersSchema(BaseModel):
    dateGte: Optional[str] = Field(default=None, description="Lower bound for publishedAt (ISO8601).")
    dateLte: Optional[str] = Field(default=None, description="Upper bound for publishedAt (ISO8601).")
    tickers: List[str] = Field(default_factory=list, description="Ticker whitelist.")
    sectors: List[str] = Field(default_factory=list, description="Sector whitelist.")
    eventTags: List[str] = Field(default_factory=list, description="Event/watchlist tags.")


class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="User question.")
    filingId: Optional[str] = Field(default=None, description="Specific filing/document focus.")
    tickers: List[str] = Field(default_factory=list, description="Primary tickers to bias retrieval.")
    sourceTypes: List[EvidenceSourceType] = Field(
        default_factory=lambda: ["filing", "news", "event"],
        description="Data sources to include.",
    )
    topK: int = Field(default=6, ge=1, le=40, description="Final evidence count returned to caller.")
    maxFilings: Optional[int] = Field(default=None, ge=1, le=20, description="Maximum number of documents to inspect.")
    enableDiff: bool = Field(default=False, description="Toggle diff post-processing.")
    filters: RagQueryFiltersSchema = Field(default_factory=RagQueryFiltersSchema)
    ragMode: Optional[str] = Field(default=None, description="Custom retrieval mode identifier.")
    sessionId: Optional[str] = Field(default=None, description="Existing chat session identifier.")
    turnId: Optional[str] = Field(default=None, description="Client supplied turn identifier.")
    userMessageId: Optional[str] = Field(default=None, description="Existing user message identifier.")
    assistantMessageId: Optional[str] = Field(default=None, description="Existing assistant message identifier.")
    retryOfMessageId: Optional[str] = Field(default=None, description="Retry pointer for previous assistant message.")
    idempotencyKey: Optional[str] = Field(default=None, description="Client generated idempotency key.")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Opaque metadata forwarded to the backend.")
    runSelfCheck: bool = Field(default=True, description="Whether to enqueue self-check once answer is produced.")


class RagWarningSchema(BaseModel):
    code: str = Field(..., description="Machine readable warning code.")
    message: str = Field(..., description="Human readable warning message.")


class RagQueryResponse(BaseModel):
    answer: Optional[str] = Field(default=None, description="LLM answer.")
    evidence: List[EvidenceSchema] = Field(default_factory=list, description="Evidence payloads.")
    warnings: List[RagWarningSchema] = Field(default_factory=list, description="Non-fatal warnings.")
    citations: Dict[str, List[Any]] = Field(default_factory=dict, description="Structured citation map.")
    sessionId: Optional[str] = Field(default=None, description="Chat session identifier.")
    turnId: Optional[str] = Field(default=None, description="Turn identifier.")
    userMessageId: Optional[str] = Field(default=None, description="User message identifier.")
    assistantMessageId: Optional[str] = Field(default=None, description="Assistant message identifier.")
    traceId: Optional[str] = Field(default=None, description="Trace/span identifier.")
    state: Optional[str] = Field(default=None, description="Assistant message state (ready/error/blocked).")
    ragMode: Optional[str] = Field(default=None, description="Retrieval strategy used.")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Model metadata (model, trace, etc).")


class RagGridRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1, description="List of companies to analyze.")
    questions: List[str] = Field(..., min_length=1, description="List of analyst questions.")
    topK: int = Field(default=4, ge=1, le=10, description="Evidence count per cell.")
    ragMode: Optional[str] = Field(default=None, description="Optional retrieval mode override.")

    @field_validator("tickers", "questions")
    @classmethod
    def _strip_items(cls, value: List[str]) -> List[str]:
        normalized = []
        for entry in value:
            text = str(entry).strip()
            if text:
                normalized.append(text)
        return normalized


class RagGridCellResponse(BaseModel):
    ticker: str
    question: str
    status: Literal["ok", "error", "pending", "running"] = "pending"
    answer: Optional[str] = None
    evidence: List[EvidenceSchema] = Field(default_factory=list)
    error: Optional[str] = None
    latencyMs: Optional[int] = Field(default=None, ge=0)


class RagGridResponse(BaseModel):
    results: List[RagGridCellResponse] = Field(default_factory=list)
    traceId: Optional[str] = Field(default=None, description="Trace/span identifier for observability.")


class RagGridJobResponse(BaseModel):
    jobId: str = Field(..., description="Job identifier.")
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    traceId: Optional[str] = Field(default=None)
    totalCells: int = Field(..., ge=0)
    completedCells: int = Field(..., ge=0)
    failedCells: int = Field(..., ge=0)
    results: List[RagGridCellResponse] = Field(default_factory=list)
    error: Optional[str] = Field(default=None)
    createdAt: Optional[str] = Field(default=None)
    updatedAt: Optional[str] = Field(default=None)


__all__ = [
    "EvidenceDiffSchema",
    "EvidenceSchema",
    "EvidenceSelfCheckSchema",
    "EvidenceSourceType",
    "RagGridCellResponse",
    "RagGridJobResponse",
    "RagGridRequest",
    "RagGridResponse",
    "RagQueryFiltersSchema",
    "RagQueryRequest",
    "RagQueryResponse",
    "RagWarningSchema",
]
