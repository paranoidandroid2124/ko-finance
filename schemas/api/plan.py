"""Pydantic schemas for plan context responses and updates."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

PlanTier = Literal["free", "starter", "pro", "enterprise"]


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
    ragCore: bool = False
    evidenceInlinePdf: bool = False
    evidenceDiff: bool = False
    timelineFull: bool = False


class PlanMemoryFlagsSchema(BaseModel):
    watchlist: bool = False
    digest: bool = False
    chat: bool = False


class PlanTrialStateSchema(BaseModel):
    tier: PlanTier = Field(default="pro", description="Trial tier that will be applied while active.")
    startsAt: Optional[str] = Field(default=None, description="ISO timestamp when the trial started.")
    endsAt: Optional[str] = Field(default=None, description="ISO timestamp when the trial is scheduled to end.")
    durationDays: Optional[int] = Field(default=None, description="Configured trial length in days.")
    active: bool = Field(default=False, description="Whether the trial perks currently override the base plan.")
    used: bool = Field(default=False, description="Indicates the trial window has already been claimed.")


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
    memoryFlags: PlanMemoryFlagsSchema = Field(
        default_factory=PlanMemoryFlagsSchema,
        description="LightMem feature toggles applied to the plan tier.",
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
    memoryFlags: PlanMemoryFlagsSchema = Field(
        default_factory=PlanMemoryFlagsSchema,
        description="Resolved LightMem feature toggles for this plan.",
    )
    trial: Optional[PlanTrialStateSchema] = Field(
        default=None,
        description="Optional trial metadata including availability and end date.",
    )


class PlanPresetSchema(BaseModel):
    tier: PlanTier = Field(..., description="Preset identifier (plan tier).")
    entitlements: list[str] = Field(default_factory=list, description="Default entitlements shipped with this tier.")
    featureFlags: PlanFeatureFlagsSchema = Field(
        default_factory=PlanFeatureFlagsSchema,
        description="Feature flags derived from the entitlement list.",
    )
    quota: PlanQuotaSchema = Field(default_factory=PlanQuotaSchema, description="Default quota values for the tier.")


class PlanPresetResponse(BaseModel):
    presets: list[PlanPresetSchema] = Field(
        default_factory=list,
        description="Collection of plan presets available to the client.",
    )


class PlanPresetUpdateRequest(BaseModel):
    tiers: list[PlanPresetSchema] = Field(
        default_factory=list,
        description="Plan tier presets to persist. Missing tiers fall back to defaults.",
    )
    updatedBy: Optional[str] = Field(
        default=None,
        description="Operator identifier stored with the update.",
    )
    note: Optional[str] = Field(
        default=None,
        description="Optional note describing the preset change.",
    )


class PlanCatalogPriceSchema(BaseModel):
    amount: float = Field(default=0.0, description="Numeric price amount for display.")
    currency: str = Field(default="KRW", description="Currency code (e.g. KRW, USD).")
    interval: str = Field(default="월", description="Billing interval label (e.g. 월, 연).")
    note: Optional[str] = Field(default=None, description="Supplementary price note displayed under the amount.")


class PlanCatalogFeatureSchema(BaseModel):
    text: str = Field(..., description="Description copy for the feature.")
    highlight: Optional[bool] = Field(default=None, description="Whether to style the feature as a highlight.")
    icon: Optional[str] = Field(default=None, description="Optional icon identifier used by the client.")


class PlanCatalogTierSchema(BaseModel):
    tier: PlanTier = Field(..., description="Plan tier identifier.")
    title: str = Field(..., description="Display title for marketing cards.")
    tagline: str = Field(..., description="Short descriptive sentence for the tier.")
    description: Optional[str] = Field(default=None, description="Longer descriptive body copy.")
    badge: Optional[str] = Field(default=None, description="Optional badge label (예: Starter, Premium).")
    price: PlanCatalogPriceSchema = Field(default_factory=PlanCatalogPriceSchema)
    ctaLabel: str = Field(..., description="CTA button label.")
    ctaHref: str = Field(..., description="CTA button link path or URL.")
    features: list[PlanCatalogFeatureSchema] = Field(default_factory=list, description="Feature bullet list.")
    imageUrl: Optional[str] = Field(default=None, description="Optional marketing image or illustration URL.")
    supportNote: Optional[str] = Field(default=None, description="Extra footnote (ex. 지원 안내).")


class PlanCatalogResponse(BaseModel):
    tiers: list[PlanCatalogTierSchema] = Field(default_factory=list, description="Plan catalog entries.")
    updatedAt: Optional[str] = Field(default=None, description="Timestamp of the latest catalog update.")
    updatedBy: Optional[str] = Field(default=None, description="Actor recorded with the latest catalog update.")
    note: Optional[str] = Field(default=None, description="Optional note stored with the last catalog update.")


class PlanCatalogUpdateRequest(BaseModel):
    tiers: list[PlanCatalogTierSchema] = Field(default_factory=list, description="Plan catalog tier definitions.")
    updatedBy: Optional[str] = Field(default=None, description="Operator recorded for the update.")
    note: Optional[str] = Field(default=None, description="Optional note describing the catalog change.")


class PlanTrialStartRequest(BaseModel):
    tier: PlanTier = Field(default="pro", description="Trial tier to activate.")
    durationDays: Optional[int] = Field(
        default=None,
        description="Override trial duration. Defaults to configured duration when omitted.",
        ge=1,
        le=30,
    )
    actor: Optional[str] = Field(
        default=None,
        description="Optional actor identifier stored in the audit log.",
        max_length=200,
    )
