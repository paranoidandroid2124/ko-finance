import type { PlanFeatureFlags, PlanQuota, PlanTier } from "@/store/planStore";

type PlanPreset = {
  entitlements: string[];
  featureFlags: PlanFeatureFlags;
  quota: PlanQuota;
};

const BASE_ENTITLEMENTS: Record<PlanTier, string[]> = {
  free: [],
  pro: ["search.compare", "search.alerts", "evidence.inline_pdf"],
  enterprise: [
    "search.compare",
    "search.alerts",
    "search.export",
    "evidence.inline_pdf",
    "evidence.diff",
    "timeline.full",
  ],
};

const BASE_QUOTA: Record<PlanTier, PlanQuota> = {
  free: {
    chatRequestsPerDay: 20,
    ragTopK: 4,
    selfCheckEnabled: false,
    peerExportRowLimit: 0,
  },
  pro: {
    chatRequestsPerDay: 500,
    ragTopK: 6,
    selfCheckEnabled: true,
    peerExportRowLimit: 100,
  },
  enterprise: {
    chatRequestsPerDay: null,
    ragTopK: 10,
    selfCheckEnabled: true,
    peerExportRowLimit: null,
  },
};

const buildFeatureFlags = (entitlements: string[]): PlanFeatureFlags => ({
  searchCompare: entitlements.includes("search.compare"),
  searchAlerts: entitlements.includes("search.alerts"),
  searchExport: entitlements.includes("search.export"),
  evidenceInlinePdf: entitlements.includes("evidence.inline_pdf"),
  evidenceDiff: entitlements.includes("evidence.diff"),
  timelineFull: entitlements.includes("timeline.full"),
});

export const PLAN_PRESETS: Record<PlanTier, PlanPreset> = {
  free: {
    entitlements: BASE_ENTITLEMENTS.free,
    featureFlags: buildFeatureFlags(BASE_ENTITLEMENTS.free),
    quota: BASE_QUOTA.free,
  },
  pro: {
    entitlements: BASE_ENTITLEMENTS.pro,
    featureFlags: buildFeatureFlags(BASE_ENTITLEMENTS.pro),
    quota: BASE_QUOTA.pro,
  },
  enterprise: {
    entitlements: BASE_ENTITLEMENTS.enterprise,
    featureFlags: buildFeatureFlags(BASE_ENTITLEMENTS.enterprise),
    quota: BASE_QUOTA.enterprise,
  },
};
