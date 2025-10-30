import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePlanStore, type PlanContextPayload } from "@/store/planStore";

vi.mock("@/lib/telemetry", () => ({
  logEvent: vi.fn(),
}));

const defaultPlanPayload: PlanContextPayload = {
  planTier: "free",
  expiresAt: null,
  entitlements: [],
  featureFlags: {
    searchCompare: false,
    searchAlerts: false,
    searchExport: false,
    evidenceInlinePdf: false,
    evidenceDiff: false,
    timelineFull: false,
  },
  quota: {
    chatRequestsPerDay: 20,
    ragTopK: 4,
    selfCheckEnabled: false,
    peerExportRowLimit: 0,
  },
};

const resetPlanStore = () => {
  const { setPlanFromServer } = usePlanStore.getState();
  setPlanFromServer(defaultPlanPayload);
  usePlanStore.setState({ initialized: false, loading: false, error: undefined });
};

describe("planStore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetPlanStore();
  });

  it("merges feature flags and quota when hydrating from server payload", () => {
    const { setPlanFromServer } = usePlanStore.getState();
    setPlanFromServer({
      planTier: "enterprise",
      expiresAt: "2026-02-01T00:00:00+00:00",
      entitlements: ["alerts.force_webhook"],
      featureFlags: {
        searchExport: true,
        timelineFull: true,
      },
      quota: {
        chatRequestsPerDay: null,
        ragTopK: 12,
        selfCheckEnabled: true,
        peerExportRowLimit: null,
      },
    });

    const state = usePlanStore.getState();
    expect(state.planTier).toBe("enterprise");
    expect(state.featureFlags.searchExport).toBe(true);
    expect(state.featureFlags.searchCompare).toBe(false);
    expect(state.featureFlags.timelineFull).toBe(true);
    expect(state.quota.chatRequestsPerDay).toBeNull();
    expect(state.quota.ragTopK).toBe(12);
    expect(state.quota.selfCheckEnabled).toBe(true);
    expect(state.quota.peerExportRowLimit).toBeNull();
    expect(state.initialized).toBe(true);
    expect(state.loading).toBe(false);
    expect(state.error).toBeUndefined();
  });

  it("fetchPlan hydrates store from API response", async () => {
    const { fetchPlan } = usePlanStore.getState();
    await fetchPlan();

    const state = usePlanStore.getState();
    expect(state.planTier).toBe("pro");
    expect(state.featureFlags.searchCompare).toBe(true);
    expect(state.featureFlags.evidenceInlinePdf).toBe(true);
    expect(state.initialized).toBe(true);
    expect(state.loading).toBe(false);
    expect(state.error).toBeUndefined();
  });

  it("fetchPlan handles failures and falls back to defaults", async () => {
    const response = new Response("server error", { status: 500 });
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(response);

    const { fetchPlan } = usePlanStore.getState();
    await fetchPlan();

    const state = usePlanStore.getState();
    expect(state.planTier).toBe("free");
    expect(state.featureFlags.searchCompare).toBe(false);
    expect(state.error).toMatch(/failed to load plan context/i);
    expect(state.initialized).toBe(true);
    expect(state.loading).toBe(false);

    fetchSpy.mockRestore();
  });
});
