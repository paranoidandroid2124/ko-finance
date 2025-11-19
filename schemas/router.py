"""Pydantic models describing SemanticRouter decisions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RouteAction(str, Enum):
    """Normalized actions that the router can trigger (derived from tool_call/safety)."""

    RAG_ANSWER = "RAG_ANSWER"
    TOOL = "TOOL"
    CLARIFY = "CLARIFY"
    BLOCK_COMPLIANCE = "BLOCK_COMPLIANCE"


class UiContainer(str, Enum):
    """UI primitives that Commander can render."""

    OVERLAY = "overlay"
    SIDE_PANEL = "side_panel"
    INLINE_CARD = "inline_card"


class PaywallTier(str, Enum):
    """Plan tier required to view full tool output."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class ToolCall(BaseModel):
    """LLM-style function call descriptor."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Unique identifier (e.g., event_study.query).")
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool-specific arguments (ticker, window, filters, ...).",
    )


class SafetyDecision(BaseModel):
    """Compliance gate output."""

    model_config = ConfigDict(extra="forbid")

    block: bool = Field(False, description="Whether output should be blocked.")
    reason: Optional[str] = Field(None, description="Human-readable reason.")
    keywords: List[str] = Field(default_factory=list, description="Triggered keywords.")


class RouteDecision(BaseModel):
    """Semantic router output consumed by downstream services."""

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(..., description="Canonical intent label (e.g., event_study, disclosure_lookup).")
    reason: str = Field(..., description="Short explanation for observability/audits.")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized confidence score (0.0 ~ 1.0).",
    )
    tool_call: ToolCall = Field(..., description="Function-style tool invocation payload.")
    ui_container: UiContainer = Field(..., description="Preferred Commander UI container.")
    paywall: PaywallTier = Field(..., description="Plan tier required for full fidelity output.")
    requires_context: List[str] = Field(
        default_factory=list,
        description="List of context providers to hydrate before tool execution.",
    )
    safety: SafetyDecision = Field(
        default_factory=SafetyDecision,
        description="Compliance gate result.",
    )
    tickers: List[str] = Field(
        default_factory=list,
        description="Normalized ticker symbols mentioned in the query.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary hints returned by the router.",
    )

    @property
    def action(self) -> RouteAction:
        """Return the derived action for backward compatibility."""

        if self.safety.block:
            return RouteAction.BLOCK_COMPLIANCE
        canonical_intent = (self.intent or "").lower()
        if canonical_intent.startswith("clarify") or self.tool_call.name == "clarify.request":
            return RouteAction.CLARIFY
        if self.tool_call.name not in {"rag.answer", "chat.answer"}:
            return RouteAction.TOOL
        return RouteAction.RAG_ANSWER

    @property
    def tool_name(self) -> str:
        """Convenience accessor for the tool call name."""

        return self.tool_call.name

    def model_dump_route(self) -> Dict[str, Any]:
        """Dump the decision payload for streaming events."""

        return self.model_dump(mode="json")
