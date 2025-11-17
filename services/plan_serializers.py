"""Shared helpers for serialising plan contexts and presets."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, cast

from schemas.api.plan import (
    PlanCatalogResponse,
    PlanCatalogTierSchema,
    PlanContextResponse,
    PlanFeatureFlagsSchema,
    PlanMemoryFlagsSchema,
    PlanPresetResponse,
    PlanPresetSchema,
    PlanQuotaSchema,
    PlanTrialStateSchema,
    PlanTier,
)
from services.plan_service import PlanContext


def _feature_flags_from_plan(plan: PlanContext) -> PlanFeatureFlagsSchema:
    flags = plan.feature_flags()
    return PlanFeatureFlagsSchema(
        searchCompare=flags.get("search.compare", False),
        searchAlerts=flags.get("search.alerts", False),
        searchExport=flags.get("search.export", False),
        ragCore=flags.get("rag.core", False),
        evidenceInlinePdf=flags.get("evidence.inline_pdf", False),
        evidenceDiff=flags.get("evidence.diff", False),
        timelineFull=flags.get("timeline.full", False),
        reportsEventExport=flags.get("reports.event_export", False),
    )


def _memory_flags_from_plan(plan: PlanContext) -> PlanMemoryFlagsSchema:
    return PlanMemoryFlagsSchema(
        watchlist=plan.memory_watchlist_enabled,
        digest=plan.memory_digest_enabled,
        chat=plan.memory_chat_enabled,
    )


def serialize_plan_context(
    plan: PlanContext,
    *,
    checkout_requested: Optional[bool] = None,
) -> PlanContextResponse:
    """Convert a ``PlanContext`` into the API response schema."""

    expires_at = plan.expires_at.isoformat() if plan.expires_at else None
    updated_at = plan.updated_at.isoformat() if plan.updated_at else None
    trial_payload = plan.trial_payload()
    trial = PlanTrialStateSchema(**trial_payload) if trial_payload else None
    checkout_flag = plan.checkout_requested if checkout_requested is None else checkout_requested

    return PlanContextResponse(
        planTier=cast(PlanTier, plan.tier),
        expiresAt=expires_at,
        entitlements=sorted(plan.entitlements),
        featureFlags=_feature_flags_from_plan(plan),
        quota=PlanQuotaSchema(**plan.quota.to_dict()),
        updatedAt=updated_at,
        updatedBy=plan.updated_by,
        changeNote=plan.change_note,
        checkoutRequested=checkout_flag,
        memoryFlags=_memory_flags_from_plan(plan),
        trial=trial,
    )


def serialize_plan_presets(presets: Sequence[Mapping[str, Any]]) -> PlanPresetResponse:
    """Normalise a list of preset payloads for API responses."""

    serialized: list[PlanPresetSchema] = []
    for preset in presets:
        feature_flags = preset.get("feature_flags") or {}
        serialized.append(
            PlanPresetSchema(
                tier=cast(PlanTier, preset["tier"]),
                entitlements=list(preset.get("entitlements") or []),
                featureFlags=PlanFeatureFlagsSchema(
                    searchCompare=bool(feature_flags.get("search.compare")),
                    searchAlerts=bool(feature_flags.get("search.alerts")),
                    searchExport=bool(feature_flags.get("search.export")),
                    ragCore=bool(feature_flags.get("rag.core")),
                    evidenceInlinePdf=bool(feature_flags.get("evidence.inline_pdf")),
                    evidenceDiff=bool(feature_flags.get("evidence.diff")),
                    timelineFull=bool(feature_flags.get("timeline.full")),
                    reportsEventExport=bool(feature_flags.get("reports.event_export")),
                ),
                quota=PlanQuotaSchema(**cast(dict[str, Any], preset.get("quota") or {})),
            )
        )
    return PlanPresetResponse(presets=serialized)


def serialize_plan_catalog(payload: Mapping[str, Any]) -> PlanCatalogResponse:
    """Normalise plan catalog dictionaries for responses."""

    tiers_payload = payload.get("tiers") or []
    tiers = [PlanCatalogTierSchema(**tier) for tier in tiers_payload]
    return PlanCatalogResponse(
        tiers=tiers,
        updatedAt=payload.get("updated_at"),
        updatedBy=payload.get("updated_by"),
        note=payload.get("note"),
    )


__all__ = [
    "serialize_plan_catalog",
    "serialize_plan_context",
    "serialize_plan_presets",
]
