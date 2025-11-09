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

export type PlanMemoryFlags = {
  watchlist: boolean;
  digest: boolean;
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

type PlanStoreState = {
  planTier: PlanTier;
  expiresAt?: string | null;
  entitlements: string[];
  featureFlags: PlanFeatureFlags;
  memoryFlags: PlanMemoryFlags;
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
  trial: PlanTrialState | null;
  trialStarting: boolean;
  trialError?: string | null;
  presets: Record<PlanTier, PlanPreset> | null;
  presetsLoading: boolean;
  presetsError?: string | null;
  fetchPlan: (options?: { signal?: AbortSignal }) => Promise<void>;
  setPlanFromServer: (payload: PlanContextPayload) => void;
  savePlan: (input: PlanContextUpdateInput) => Promise<PlanContextPayload>;
  startTrial: (input?: PlanTrialStartInput) => Promise<PlanContextPayload>;
  fetchPlanPresets: (options?: { signal?: AbortSignal }) => Promise<void>;
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

const DEFAULT_MEMORY_FLAGS: PlanMemoryFlags = {
  watchlist: false,
  digest: false,
  chat: false,
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
  memoryFlags: DEFAULT_MEMORY_FLAGS,
  quota: DEFAULT_QUOTA,
  updatedAt: null,
  updatedBy: null,
  changeNote: null,
  checkoutRequested: false,
  trial: {
    tier: 'pro',
    startsAt: null,
    endsAt: null,
    durationDays: 7,
    active: false,
    used: false,
  },
};

function mergeFeatureFlags(flags?: PlanFeatureFlags): PlanFeatureFlags {
  return { ...DEFAULT_FEATURE_FLAGS, ...(flags ?? {}) };
}

function mergeMemoryFlags(flags?: PlanMemoryFlags): PlanMemoryFlags {
  return { ...DEFAULT_MEMORY_FLAGS, ...(flags ?? {}) };
}

function mergeQuota(quota?: PlanQuota): PlanQuota {
  return { ...DEFAULT_QUOTA, ...(quota ?? {}) };
}

const DEFAULT_TRIAL_STATE: PlanTrialState = {
  tier: 'pro',
  startsAt: null,
  endsAt: null,
  durationDays: 7,
  active: false,
  used: false,
};

function mergeTrial(trial?: PlanTrialState | null): PlanTrialState {
  if (!trial) {
    return { ...DEFAULT_TRIAL_STATE };
  }
  return {
    tier: trial.tier ?? DEFAULT_TRIAL_STATE.tier,
    startsAt: trial.startsAt ?? null,
    endsAt: trial.endsAt ?? null,
    durationDays: trial.durationDays ?? DEFAULT_TRIAL_STATE.durationDays,
    active: Boolean(trial.active),
    used: Boolean(trial.used),
  };
}

type PlanPresetResponsePayload = {
  presets: Array<{
    tier: PlanTier;
    entitlements?: string[];
    featureFlags?: PlanFeatureFlags;
    quota?: PlanQuota;
  }>;
};

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
    memoryFlags: mergeMemoryFlags(payload.memoryFlags),
    quota: mergeQuota(payload.quota),
    updatedAt: payload.updatedAt ?? null,
    updatedBy: payload.updatedBy ?? null,
    changeNote: payload.changeNote ?? null,
    checkoutRequested: payload.checkoutRequested ?? false,
    trial: mergeTrial(payload.trial),
  };
}

export const usePlanStore = create<PlanStoreState>((set, get) => ({
  planTier: DEFAULT_PLAN_PAYLOAD.planTier,
  expiresAt: DEFAULT_PLAN_PAYLOAD.expiresAt,
  entitlements: DEFAULT_PLAN_PAYLOAD.entitlements,
  featureFlags: DEFAULT_FEATURE_FLAGS,
  memoryFlags: DEFAULT_MEMORY_FLAGS,
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
  trial: mergeTrial(DEFAULT_PLAN_PAYLOAD.trial),
  trialStarting: false,
  trialError: undefined,
  presets: null,
  presetsLoading: false,
  presetsError: undefined,

  async fetchPlan(options) {
    if (get().loading) {
      return;
    }
    set({ loading: true, error: undefined });

    try {
      const baseUrl = resolveApiBase();
      const response = await fetch(`${baseUrl}/api/v1/plan/context`, {
        cache: 'no-store',
        credentials: 'include',
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
        memoryFlags: mapped.memoryFlags,
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
        trial: mapped.trial,
        trialStarting: false,
        trialError: undefined,
      });
      if (!get().presets && !get().presetsLoading) {
        void get()
          .fetchPlanPresets(options)
          .catch(() => undefined);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'plan context fetch failed';
      logEvent('plan.context.fetch_failed', { message });

      set({
        planTier: DEFAULT_PLAN_PAYLOAD.planTier,
        expiresAt: DEFAULT_PLAN_PAYLOAD.expiresAt,
        entitlements: DEFAULT_PLAN_PAYLOAD.entitlements,
        featureFlags: DEFAULT_FEATURE_FLAGS,
        memoryFlags: DEFAULT_MEMORY_FLAGS,
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
        trial: mergeTrial(DEFAULT_PLAN_PAYLOAD.trial),
        trialStarting: false,
        trialError: message,
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
      memoryFlags: mapped.memoryFlags,
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
      trial: mapped.trial,
      trialStarting: false,
      trialError: undefined,
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
        memoryFlags: current.memoryFlags,
        quota: current.quota,
        updatedAt: current.updatedAt ?? null,
        updatedBy: current.updatedBy ?? null,
        changeNote: current.changeNote ?? null,
        checkoutRequested: current.checkoutRequested,
        trial: current.trial ?? mergeTrial(DEFAULT_PLAN_PAYLOAD.trial),
      });
    }
    set({ saving: true, saveError: undefined });

    const baseUrl = resolveApiBase();
    const unique = uniqueEntitlements(input.entitlements);
    const body = {
      planTier: input.planTier,
      expiresAt: input.expiresAt ?? null,
      entitlements: unique,
      memoryFlags: input.memoryFlags ?? DEFAULT_MEMORY_FLAGS,
      quota: input.quota,
      updatedBy: input.updatedBy ?? null,
      changeNote: input.changeNote ?? null,
      triggerCheckout: Boolean(input.triggerCheckout),
    };

    try {
      const response = await fetch(`${baseUrl}/api/v1/plan/context`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
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
        memoryFlags: mapped.memoryFlags,
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
        trial: mapped.trial,
        trialStarting: false,
        trialError: undefined,
      });

      return payload;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'plan context save failed';
      logEvent('plan.context.save_failed', { message });
      set({ saving: false, saveError: message });
      throw error instanceof Error ? error : new Error(String(error));
    }
  },

  async startTrial(input) {
    const { trialStarting } = get();
    if (trialStarting) {
      return Promise.reject(new Error('trial request already in progress'));
    }
    set({ trialStarting: true, trialError: undefined });

    const baseUrl = resolveApiBase();
    const payloadBody: Record<string, unknown> = {};
    if (input?.actor) {
      payloadBody.actor = input.actor;
    }
    if (typeof input?.durationDays === 'number') {
      payloadBody.durationDays = input.durationDays;
    }
    if (input?.tier) {
      payloadBody.tier = input.tier;
    }

    try {
      const response = await fetch(`${baseUrl}/api/v1/plan/trial`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payloadBody),
      });

      if (!response.ok) {
        throw new Error(`failed to start plan trial (${response.status})`);
      }

      const payload = (await response.json()) as PlanContextPayload;
      const mapped = mapPayload(payload);
      logEvent('plan.trial.started', {
        planTier: mapped.planTier,
        trialTier: mapped.trial.tier,
        trialActive: mapped.trial.active,
      });

      set({
        planTier: mapped.planTier,
        expiresAt: mapped.expiresAt,
        entitlements: mapped.entitlements,
        featureFlags: mapped.featureFlags,
        memoryFlags: mapped.memoryFlags,
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
        trial: mapped.trial,
        trialStarting: false,
        trialError: undefined,
      });

      return payload;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'plan trial request failed';
      logEvent('plan.trial.failed', { message });
      set({ trialStarting: false, trialError: message });
      throw error instanceof Error ? error : new Error(String(error));
    }
  },

  async fetchPlanPresets(options) {
    if (get().presetsLoading) {
      return;
    }
    set({ presetsLoading: true, presetsError: undefined });
    try {
      const baseUrl = resolveApiBase();
      const response = await fetch(`${baseUrl}/api/v1/plan/presets`, {
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        signal: options?.signal,
      });
      if (!response.ok) {
        throw new Error(`failed to load plan presets (${response.status})`);
      }
      const payload = (await response.json()) as PlanPresetResponsePayload;
      const mapping = payload.presets.reduce((acc, preset) => {
        const tier = preset.tier;
        const normalized: PlanPreset = {
          tier,
          entitlements: uniqueEntitlements(preset.entitlements ?? []),
          featureFlags: mergeFeatureFlags(preset.featureFlags),
          quota: mergeQuota(preset.quota ?? undefined),
        };
        acc[tier] = normalized;
        return acc;
      }, {} as Record<PlanTier, PlanPreset>);
      set({
        presets: mapping,
        presetsLoading: false,
        presetsError: undefined,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'plan preset fetch failed';
      set({ presetsLoading: false, presetsError: message });
      throw error instanceof Error ? error : new Error(String(error));
    }
  },
}));

export const usePlanTier = () => usePlanStore((state) => state.planTier);
export const usePlanTrial = () => usePlanStore((state) => state.trial);
export const usePlanTrialRequestState = () =>
  usePlanStore((state) => ({
    trialStarting: state.trialStarting,
    trialError: state.trialError,
  }));
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
