"""Pydantic models describing SemanticRouter decisions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class RouteAction(str, Enum):
    """Normalized actions that the router can trigger."""

    RAG_ANSWER = "RAG_ANSWER"
    TOOL_DISCLOSURE = "TOOL_DISCLOSURE"
    TOOL_NEWS = "TOOL_NEWS"
    TOOL_EVENT_STUDY = "TOOL_EVENT_STUDY"
    TOOL_MARKET_BRIEF = "TOOL_MARKET_BRIEF"
    CLARIFY = "CLARIFY"
    BLOCK_COMPLIANCE = "BLOCK_COMPLIANCE"


class RouteSuggestion(BaseModel):
    """Alternative actions surfaced when confidence is low."""

    model_config = ConfigDict(extra="forbid")

    action: RouteAction = Field(..., description="Action executed when the user selects this suggestion.")
    label: str = Field(..., description="Short UI label for chips or buttons.")
    reason: Optional[str] = Field(
        None,
        description="Optional hint explaining when this suggestion is useful.",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool-specific parameters applied if the suggestion is executed.",
    )


class RouteDecision(BaseModel):
    """Semantic router output consumed by downstream services."""

    model_config = ConfigDict(extra="forbid")

    action: RouteAction = Field(..., description="Primary action that the chat orchestrator should run.")
    reason: str = Field(..., description="Concise explanation for observability and audits.")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized confidence score (0.0 ~ 1.0).",
    )
    intent: Optional[str] = Field(
        None,
        description="Optional canonical intent label (e.g., earnings_reaction, disclosure_lookup).",
    )
    tickers: List[str] = Field(
        default_factory=list,
        description="Normalized ticker symbols mentioned in the query.",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool-specific arguments such as event type or date range.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured hints returned by the router.",
    )
    suggestions: List[RouteSuggestion] = Field(
        default_factory=list,
        description="Alternative actions to show as chips when clarification is required.",
    )
    blocked_phrases: List[str] = Field(
        default_factory=list,
        description="Regulatory trigger phrases when action=BLOCK_COMPLIANCE.",
    )

