"use client";

export type PlanTier = "free" | "starter" | "pro" | "enterprise";

export type PlanFeatureFlags = {
  searchCompare: boolean;
  searchExport: boolean;
  ragCore: boolean;
  evidenceInlinePdf: boolean;
  evidenceDiff: boolean;
  timelineFull: boolean;
  reportsEventExport: boolean;
};

export type PlanMemoryFlags = {
  chat: boolean;
};

export type PlanQuota = {
  chatRequestsPerDay: number | null;
  ragTopK: number | null;
  selfCheckEnabled: boolean;
  peerExportRowLimit: number | null;
};

export type PlanTrialState = {
  tier: PlanTier;
  startsAt: string | null;
  endsAt: string | null;
  durationDays?: number | null;
  active: boolean;
  used: boolean;
};

export type PlanTrialStartInput = {
  actor?: string | null;
  durationDays?: number | null;
  tier?: PlanTier;
};

export type PlanPreset = {
  tier: PlanTier;
  entitlements: string[];
  featureFlags: PlanFeatureFlags;
  quota: PlanQuota;
};

export type PlanCatalogFeature = {
  text: string;
  highlight?: boolean | null;
  icon?: string | null;
};

export type PlanCatalogPrice = {
  amount: number;
  currency: string;
  interval: string;
  note?: string | null;
};

export type PlanCatalogTier = {
  tier: PlanTier;
  title: string;
  tagline: string;
  description?: string | null;
  badge?: string | null;
  price: PlanCatalogPrice;
  ctaLabel: string;
  ctaHref: string;
  upgradePath?: string | null;
  features: PlanCatalogFeature[];
  imageUrl?: string | null;
  supportNote?: string | null;
};

export type PlanCatalogPayload = {
  tiers: PlanCatalogTier[];
  updatedAt?: string | null;
  updatedBy?: string | null;
  note?: string | null;
};

export type PlanContextPayload = {
  planTier: PlanTier;
  expiresAt?: string | null;
  entitlements: string[];
  featureFlags: PlanFeatureFlags;
  memoryFlags: PlanMemoryFlags;
  quota: PlanQuota;
  updatedAt?: string | null;
  updatedBy?: string | null;
  changeNote?: string | null;
  checkoutRequested?: boolean;
  trial?: PlanTrialState | null;
};

export type PlanContextUpdateInput = {
  planTier: PlanTier;
  expiresAt?: string | null;
  entitlements: string[];
  memoryFlags: PlanMemoryFlags;
  quota: PlanQuota;
  updatedBy?: string | null;
  changeNote?: string | null;
  triggerCheckout?: boolean;
};

export type PlanDebugOverride = {
  enabled: boolean;
  planTier?: PlanTier;
  entitlements?: string[];
  featureFlags?: Partial<PlanFeatureFlags>;
  memoryFlags?: Partial<PlanMemoryFlags>;
  quota?: Partial<PlanQuota>;
  expiresAt?: string | null;
  checkoutRequested?: boolean;
};
