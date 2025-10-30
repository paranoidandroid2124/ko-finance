'use client';

import { create } from 'zustand';
import { logEvent } from '@/lib/telemetry';
import { resolveApiBase } from '@/lib/apiBase';

export type PlanTier = 'free' | 'pro' | 'enterprise';

export type PlanFeatureFlags = {
  searchCompare: boolean;
  searchAlerts: boolean;
  searchExport: boolean;
  evidenceInlinePdf: boolean;
  evidenceDiff: boolean;
  timelineFull: boolean;
};

export type PlanQuota = {
  chatRequestsPerDay: number | null;
  ragTopK: number | null;
  selfCheckEnabled: boolean;
  peerExportRowLimit: number | null;
};

export type PlanContextPayload = {
  planTier: PlanTier;
  expiresAt?: string | null;
  entitlements: string[];
  featureFlags: PlanFeatureFlags;
  quota: PlanQuota;
  updatedAt?: string | null;
  updatedBy?: string | null;
  changeNote?: string | null;
  checkoutRequested?: boolean;
};

export type PlanContextUpdateInput = {
  planTier: PlanTier;
  expiresAt?: string | null;
  entitlements: string[];
  quota: PlanQuota;
  updatedBy?: string | null;
  changeNote?: string | null;
  triggerCheckout?: boolean;
};

type PlanStoreState = {
  planTier: PlanTier;
  expiresAt?: string | null;
  entitlements: string[];
  featureFlags: PlanFeatureFlags;
  quota: PlanQuota;
  updatedAt?: string | null;
  updatedBy?: string | null;
  changeNote?: string | null;
  checkoutRequested: boolean;
  initialized: boolean;
  loading: boolean;
  saving: boolean;
  error?: string | null;
  saveError?: string | null;
  fetchPlan: (options?: { signal?: AbortSignal }) => Promise<void>;
  setPlanFromServer: (payload: PlanContextPayload) => void;
  savePlan: (input: PlanContextUpdateInput) => Promise<PlanContextPayload>;
};

const PLAN_TIER_ORDER: Record<PlanTier, number> = {
  free: 0,
  pro: 1,
  enterprise: 2,
};

const DEFAULT_FEATURE_FLAGS: PlanFeatureFlags = {
  searchCompare: false,
  searchAlerts: false,
  searchExport: false,
  evidenceInlinePdf: false,
  evidenceDiff: false,
  timelineFull: false,
};

const DEFAULT_QUOTA: PlanQuota = {
  chatRequestsPerDay: 20,
  ragTopK: 4,
  selfCheckEnabled: false,
  peerExportRowLimit: 0,
};

const DEFAULT_PLAN_PAYLOAD: PlanContextPayload = {
  planTier: 'free',
  expiresAt: null,
  entitlements: [],
  featureFlags: DEFAULT_FEATURE_FLAGS,
  quota: DEFAULT_QUOTA,
  updatedAt: null,
  updatedBy: null,
  changeNote: null,
  checkoutRequested: false,
};

function mergeFeatureFlags(flags?: PlanFeatureFlags): PlanFeatureFlags {
  return { ...DEFAULT_FEATURE_FLAGS, ...(flags ?? {}) };
}

function mergeQuota(quota?: PlanQuota): PlanQuota {
  return { ...DEFAULT_QUOTA, ...(quota ?? {}) };
}

function uniqueEntitlements(entitlements?: string[]): string[] {
  if (!entitlements?.length) {
    return [];
  }
  const seen = new Set<string>();
  const result: string[] = [];
  entitlements.forEach((item) => {
    const trimmed = item.trim();
    if (!trimmed || seen.has(trimmed)) {
      return;
    }
    seen.add(trimmed);
    result.push(trimmed);
  });
  return result;
}

function mapPayload(payload: PlanContextPayload) {
  return {
    planTier: payload.planTier,
    expiresAt: payload.expiresAt ?? null,
    entitlements: uniqueEntitlements(payload.entitlements),
    featureFlags: mergeFeatureFlags(payload.featureFlags),
    quota: mergeQuota(payload.quota),
    updatedAt: payload.updatedAt ?? null,
    updatedBy: payload.updatedBy ?? null,
    changeNote: payload.changeNote ?? null,
    checkoutRequested: payload.checkoutRequested ?? false,
  };
}

export const usePlanStore = create<PlanStoreState>((set, get) => ({
  planTier: DEFAULT_PLAN_PAYLOAD.planTier,
  expiresAt: DEFAULT_PLAN_PAYLOAD.expiresAt,
  entitlements: DEFAULT_PLAN_PAYLOAD.entitlements,
  featureFlags: DEFAULT_FEATURE_FLAGS,
  quota: DEFAULT_QUOTA,
  updatedAt: DEFAULT_PLAN_PAYLOAD.updatedAt,
  updatedBy: DEFAULT_PLAN_PAYLOAD.updatedBy,
  changeNote: DEFAULT_PLAN_PAYLOAD.changeNote,
  checkoutRequested: DEFAULT_PLAN_PAYLOAD.checkoutRequested ?? false,
  initialized: false,
  loading: false,
  saving: false,
  error: undefined,
  saveError: undefined,

  async fetchPlan(options) {
    if (get().loading) {
      return;
    }
    set({ loading: true, error: undefined });

    try {
      const baseUrl = resolveApiBase();
      const response = await fetch(`${baseUrl}/api/v1/plan/context`, {
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: options?.signal,
      });

      if (!response.ok) {
        throw new Error(`failed to load plan context (${response.status})`);
      }

      const payload = (await response.json()) as PlanContextPayload;
      logEvent('plan.context.fetched', {
        planTier: payload.planTier,
        entitlements: payload.entitlements ?? [],
      });

      const mapped = mapPayload(payload);
      set({
        planTier: mapped.planTier,
        expiresAt: mapped.expiresAt,
        entitlements: mapped.entitlements,
        featureFlags: mapped.featureFlags,
        quota: mapped.quota,
        updatedAt: mapped.updatedAt,
        updatedBy: mapped.updatedBy,
        changeNote: mapped.changeNote,
        checkoutRequested: mapped.checkoutRequested,
        initialized: true,
        loading: false,
        saving: false,
        error: undefined,
        saveError: undefined,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'plan context fetch failed';
      logEvent('plan.context.fetch_failed', { message });

      set({
        planTier: DEFAULT_PLAN_PAYLOAD.planTier,
        expiresAt: DEFAULT_PLAN_PAYLOAD.expiresAt,
        entitlements: DEFAULT_PLAN_PAYLOAD.entitlements,
        featureFlags: DEFAULT_FEATURE_FLAGS,
        quota: DEFAULT_QUOTA,
        updatedAt: DEFAULT_PLAN_PAYLOAD.updatedAt,
        updatedBy: DEFAULT_PLAN_PAYLOAD.updatedBy,
        changeNote: DEFAULT_PLAN_PAYLOAD.changeNote,
        checkoutRequested: DEFAULT_PLAN_PAYLOAD.checkoutRequested ?? false,
        initialized: true,
        loading: false,
        saving: false,
        error: message,
        saveError: message,
      });
    }
  },

  setPlanFromServer(payload) {
    logEvent('plan.context.hydrated', { planTier: payload.planTier });
    const mapped = mapPayload(payload);
    set({
      planTier: mapped.planTier,
      expiresAt: mapped.expiresAt,
      entitlements: mapped.entitlements,
      featureFlags: mapped.featureFlags,
      quota: mapped.quota,
      updatedAt: mapped.updatedAt,
      updatedBy: mapped.updatedBy,
      changeNote: mapped.changeNote,
      checkoutRequested: mapped.checkoutRequested,
      initialized: true,
      loading: false,
      saving: false,
      error: undefined,
      saveError: undefined,
    });
  },

  async savePlan(input) {
    const current = get();
    if (current.saving) {
      return Promise.resolve({
        planTier: current.planTier,
        expiresAt: current.expiresAt ?? null,
        entitlements: current.entitlements,
        featureFlags: current.featureFlags,
        quota: current.quota,
        updatedAt: current.updatedAt ?? null,
        updatedBy: current.updatedBy ?? null,
        changeNote: current.changeNote ?? null,
        checkoutRequested: current.checkoutRequested,
      });
    }
    set({ saving: true, saveError: undefined });

    const baseUrl = resolveApiBase();
    const unique = uniqueEntitlements(input.entitlements);
    const body = {
      planTier: input.planTier,
      expiresAt: input.expiresAt ?? null,
      entitlements: unique,
      quota: input.quota,
      updatedBy: input.updatedBy ?? null,
      changeNote: input.changeNote ?? null,
      triggerCheckout: Boolean(input.triggerCheckout),
    };

    try {
      const response = await fetch(`${baseUrl}/api/v1/plan/context`, {
        method: 'PATCH',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-Admin-Role': 'admin',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const message = `failed to save plan context (${response.status})`;
        throw new Error(message);
      }

      const payload = (await response.json()) as PlanContextPayload;
      const mapped = mapPayload(payload);
      logEvent('plan.context.saved', {
        planTier: mapped.planTier,
        entitlements: mapped.entitlements,
        checkoutRequested: mapped.checkoutRequested,
      });

      set({
        planTier: mapped.planTier,
        expiresAt: mapped.expiresAt,
        entitlements: mapped.entitlements,
        featureFlags: mapped.featureFlags,
        quota: mapped.quota,
        updatedAt: mapped.updatedAt,
        updatedBy: mapped.updatedBy ?? body.updatedBy ?? null,
        changeNote: mapped.changeNote ?? body.changeNote ?? null,
        checkoutRequested: mapped.checkoutRequested,
        initialized: true,
        loading: false,
        saving: false,
        error: undefined,
        saveError: undefined,
      });

      return payload;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'plan context save failed';
      logEvent('plan.context.save_failed', { message });
      set({ saving: false, saveError: message });
      throw error instanceof Error ? error : new Error(String(error));
    }
  },
}));

export const usePlanTier = () => usePlanStore((state) => state.planTier);
export const usePlanFeatureFlag = <K extends keyof PlanFeatureFlags>(flag: K) =>
  usePlanStore((state) => state.featureFlags[flag]);

export const planTierRank = (tier: PlanTier): number => PLAN_TIER_ORDER[tier] ?? 0;
export const isTierAtLeast = (tier: PlanTier, required: PlanTier): boolean =>
  planTierRank(tier) >= planTierRank(required);
export const nextTier = (tier: PlanTier): PlanTier | null => {
  if (tier === 'free') {
    return 'pro';
  }
  if (tier === 'pro') {
    return 'enterprise';
  }
  return null;
};
