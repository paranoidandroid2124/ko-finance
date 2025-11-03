"""Pydantic schemas for plan context responses and updates."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

PlanTier = Literal["free", "pro", "enterprise"]


class PlanQuotaSchema(BaseModel):
    chatRequestsPerDay: Optional[int] = Field(
        default=None,
        description="Daily chat request allowance. Null means unlimited.",
    )
    ragTopK: Optional[int] = Field(
        default=None,
        description="Maximum RAG top_k value. Null means default preset.",
    )
    selfCheckEnabled: bool = Field(default=False, description="Whether self-check metadata is enabled.")
    peerExportRowLimit: Optional[int] = Field(
        default=None,
        description="Row limit for peer CSV exports. Null means unlimited.",
    )


class PlanFeatureFlagsSchema(BaseModel):
    searchCompare: bool = False
    searchAlerts: bool = False
    searchExport: bool = False
    evidenceInlinePdf: bool = False
    evidenceDiff: bool = False
    timelineFull: bool = False


class PlanContextUpdateRequest(BaseModel):
    planTier: PlanTier = Field(..., description="Desired default plan tier.")
    expiresAt: Optional[str] = Field(
        default=None,
        description="Optional ISO8601 expiration timestamp applied to the default plan context.",
    )
    entitlements: list[str] = Field(
        default_factory=list,
        description="Canonical entitlement list saved for the plan tier.",
    )
    quota: PlanQuotaSchema = Field(
        default_factory=PlanQuotaSchema,
        description="Quota overrides applied to the selected plan tier.",
    )
    updatedBy: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Operator identifier recorded with the change.",
    )
    changeNote: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional note describing the reason for the update.",
    )
    triggerCheckout: bool = Field(
        default=False,
        description="Set true to begin Toss Payments checkout after saving.",
    )

    @field_validator("entitlements", mode="before")
    def _normalize_entitlements(cls, value: Optional[list[str]]) -> list[str]:
        if not value:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item).strip()
            if not text or text in seen:
                continue
            normalized.append(text)
            seen.add(text)
        return normalized


class PlanContextResponse(BaseModel):
    planTier: PlanTier = Field(..., description="Resolved plan tier for the current session.")
    expiresAt: Optional[str] = Field(default=None, description="ISO formatted plan expiration timestamp.")
    entitlements: list[str] = Field(default_factory=list, description="Feature entitlements enabled for this plan.")
    featureFlags: PlanFeatureFlagsSchema = Field(default_factory=PlanFeatureFlagsSchema)
    quota: PlanQuotaSchema = Field(default_factory=PlanQuotaSchema)
    updatedAt: Optional[str] = Field(default=None, description="Last saved timestamp for the plan settings.")
    updatedBy: Optional[str] = Field(default=None, description="Operator recorded with the last plan update.")
    changeNote: Optional[str] = Field(default=None, description="Admin-provided note for the latest plan change.")
    checkoutRequested: bool = Field(
        default=False,
        description="Indicates the caller requested a Toss Payments checkout as part of this response.",
    )
