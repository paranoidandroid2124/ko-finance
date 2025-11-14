"use client";

import type { PlanTier } from "./types";
import { FEATURE_STARTER_ENABLED } from "@/config/features";

const PLAN_TIER_ORDER: Record<PlanTier, number> = {
  free: 0,
  starter: 1,
  pro: 2,
  enterprise: 3,
};

export const planTierRank = (tier: PlanTier): number => PLAN_TIER_ORDER[tier] ?? 0;

export const isTierAtLeast = (tier: PlanTier, required: PlanTier): boolean =>
  planTierRank(tier) >= planTierRank(required);

export const nextTier = (tier: PlanTier): PlanTier | null => {
  if (tier === "free") {
    return FEATURE_STARTER_ENABLED ? "starter" : "pro";
  }
  if (tier === "starter") {
    return "pro";
  }
  if (tier === "pro") {
    return "enterprise";
  }
  return null;
};
