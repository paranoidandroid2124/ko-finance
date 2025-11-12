import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePlanStore, type PlanContextPayload, type PlanFeatureFlags } from "@/store/planStore";

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
    ragCore: false,
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
  memoryFlags: {
    watchlist: false,
    digest: false,
    chat: false,
  },
  trial: {
    tier: "pro",
    startsAt: null,
    endsAt: null,
    durationDays: 7,
    active: false,
    used: false,
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
    const mergedFlags: PlanFeatureFlags = {
      searchCompare: false,
      searchAlerts: false,
      searchExport: true,
      ragCore: true,
      evidenceInlinePdf: false,
      evidenceDiff: false,
      timelineFull: true,
    };
    setPlanFromServer({
      planTier: "enterprise",
      expiresAt: "2026-02-01T00:00:00+00:00",
      entitlements: ["alerts.force_webhook"],
      featureFlags: mergedFlags,
      memoryFlags: {
        watchlist: true,
        digest: true,
        chat: false,
      },
      quota: {
        chatRequestsPerDay: null,
        ragTopK: 12,
        selfCheckEnabled: true,
        peerExportRowLimit: null,
      },
      trial: {
        tier: "pro",
        startsAt: null,
        endsAt: null,
        durationDays: 7,
        active: false,
        used: true,
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

  it("startTrial hydrates store with trial metadata", async () => {
    const trialPayload: PlanContextPayload = {
      planTier: "pro",
      expiresAt: null,
      entitlements: ["search.compare", "search.alerts", "search.export", "rag.core"],
      featureFlags: {
        searchCompare: true,
        searchAlerts: true,
        searchExport: false,
        ragCore: true,
        evidenceInlinePdf: true,
        evidenceDiff: false,
        timelineFull: false,
      },
      memoryFlags: defaultPlanPayload.memoryFlags,
      quota: defaultPlanPayload.quota,
      trial: {
        tier: "pro",
        startsAt: "2025-01-01T00:00:00+00:00",
        endsAt: "2025-01-08T00:00:00+00:00",
        durationDays: 7,
        active: true,
        used: true,
      },
    };
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(trialPayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const { startTrial } = usePlanStore.getState();
    await startTrial({ actor: "tester@ko.finance" });

    const state = usePlanStore.getState();
    expect(state.trial?.active).toBe(true);
    expect(state.trial?.used).toBe(true);
    expect(state.trialStarting).toBe(false);
    expect(state.trialError).toBeUndefined();

    fetchSpy.mockRestore();
  });

  it("startTrial stores error message on failure", async () => {
    const fetchSpy = vi
      .spyOn(global, "fetch")
      .mockResolvedValueOnce(new Response("blocked", { status: 400 }));

    const { startTrial } = usePlanStore.getState();
    await expect(startTrial()).rejects.toThrow(/failed to start plan trial/i);

    const state = usePlanStore.getState();
    expect(state.trialStarting).toBe(false);
    expect(state.trialError).toMatch(/failed to start plan trial/i);

    fetchSpy.mockRestore();
  });
});
