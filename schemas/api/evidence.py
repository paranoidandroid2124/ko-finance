"""Pydantic schemas for evidence workspace endpoints."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from schemas.api.rag import RAGEvidence


class EvidenceWorkspaceDiffSchema(BaseModel):
    enabled: bool = Field(default=False, description="Whether diff mode is available.")
    removed: List[RAGEvidence] = Field(default_factory=list, description="Evidence removed since last snapshot.")


class EvidenceWorkspaceResponse(BaseModel):
    traceId: str = Field(..., description="Trace identifier associated with this evidence set.")
    evidence: List[RAGEvidence] = Field(default_factory=list, description="Evidence entries for the trace.")
    diff: EvidenceWorkspaceDiffSchema = Field(default_factory=EvidenceWorkspaceDiffSchema)
    pdfUrl: Optional[str] = Field(default=None, description="Primary PDF viewer URL (if available).")
    pdfDownloadUrl: Optional[str] = Field(default=None, description="Download URL for the PDF.")
    selectedUrnId: Optional[str] = Field(default=None, description="URN to preselect when rendering the workspace.")


__all__ = ["EvidenceWorkspaceDiffSchema", "EvidenceWorkspaceResponse"]
