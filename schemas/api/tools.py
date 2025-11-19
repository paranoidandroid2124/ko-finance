"""Schemas for tool-specific APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ToolMemoryWriteRequest(BaseModel):
    """Payload emitted by Commander tools to persist LightMem summaries."""

    sessionId: UUID
    turnId: UUID
    toolId: str = Field(..., max_length=64)
    topic: str = Field(..., max_length=512)
    question: Optional[str] = Field(None, max_length=1000)
    answer: Optional[str] = Field(None, max_length=2000)
    highlights: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolMemoryWriteResponse(BaseModel):
    """Result of attempting to store a LightMem summary for a tool."""

    stored: bool
    reason: Optional[str] = None
