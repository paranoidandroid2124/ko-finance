'use client';

import { create } from 'zustand';
import { logEvent } from '@/lib/telemetry';
import { resolveApiBase } from '@/lib/apiBase';
import { fetchWithAuth } from '@/lib/fetchWithAuth';
import {
  type PlanContextPayload,
  type PlanContextUpdateInput,
  type PlanDebugOverride,
  type PlanFeatureFlags,
  type PlanMemoryFlags,
  type PlanPreset,
  type PlanQuota,
  type PlanTier,
  type PlanTrialStartInput,
  type PlanTrialState,
} from '@/store/planStore/types';
import { isTierAtLeast, nextTier, planTierRank } from '@/store/planStore/helpers';

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
  lastServerPlan: NormalizedPlanContext;
  debugToolsEnabled: boolean;
  debugOverride: PlanDebugOverride | null;
  fetchPlan: (options?: { signal?: AbortSignal }) => Promise<void>;
  setPlanFromServer: (payload: PlanContextPayload) => void;
  savePlan: (input: PlanContextUpdateInput) => Promise<PlanContextPayload>;
  startTrial: (input?: PlanTrialStartInput) => Promise<PlanContextPayload>;
  fetchPlanPresets: (options?: { signal?: AbortSignal }) => Promise<void>;
  applyDebugOverride: (override: PlanDebugOverride) => void;
  clearDebugOverride: () => void;
};

const DEFAULT_FEATURE_FLAGS: PlanFeatureFlags = {
  searchCompare: false,
  searchAlerts: false,
  searchExport: false,
  ragCore: false,
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

const PLAN_DEBUG_STORAGE_KEY = '__ko_plan_debug_override__';
const PLAN_DEBUG_TOOLS_ENABLED =
  process.env.NEXT_PUBLIC_ENABLE_PLAN_DEBUG_TOOLS === '1' ||
  (process.env.NEXT_PUBLIC_ENABLE_PLAN_DEBUG_TOOLS !== '0' && process.env.NODE_ENV !== 'production');

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

export type PlanPresetResponsePayload = {
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

type NormalizedPlanContext = ReturnType<typeof mapPayload>;

const DEFAULT_NORMALIZED_PLAN: NormalizedPlanContext = mapPayload(DEFAULT_PLAN_PAYLOAD);

const readDebugOverrideFromStorage = (): PlanDebugOverride | null => {
  if (!PLAN_DEBUG_TOOLS_ENABLED || typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(PLAN_DEBUG_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as PlanDebugOverride;
    if (!parsed?.enabled) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
};

const persistDebugOverrideToStorage = (override: PlanDebugOverride | null) => {
  if (typeof window === 'undefined') {
    return;
  }
  if (!override || !override.enabled) {
    window.localStorage.removeItem(PLAN_DEBUG_STORAGE_KEY);
    return;
  }
  try {
    window.localStorage.setItem(PLAN_DEBUG_STORAGE_KEY, JSON.stringify(override));
  } catch {
    // noop - storage quota exceeded or unavailable
  }
};

const applyDebugOverrideToPayload = (
  payload: NormalizedPlanContext,
  override: PlanDebugOverride | null,
): NormalizedPlanContext => {
  if (!PLAN_DEBUG_TOOLS_ENABLED || !override?.enabled) {
    return payload;
  }

  const next: NormalizedPlanContext = { ...payload };

  if (override.planTier) {
    next.planTier = override.planTier;
  }

  if (override.entitlements?.length) {
    next.entitlements = uniqueEntitlements([...next.entitlements, ...override.entitlements]);
  }

  if (override.featureFlags) {
    next.featureFlags = mergeFeatureFlags({
      ...next.featureFlags,
      ...override.featureFlags,
    } as PlanFeatureFlags);
  }

  if (override.memoryFlags) {
    next.memoryFlags = mergeMemoryFlags({
      ...next.memoryFlags,
      ...override.memoryFlags,
    } as PlanMemoryFlags);
  }

  if (override.quota) {
    next.quota = mergeQuota({
      ...next.quota,
      ...override.quota,
    } as PlanQuota);
  }

  if (override.expiresAt !== undefined) {
    next.expiresAt = override.expiresAt ?? null;
  }

  if (typeof override.checkoutRequested === 'boolean') {
    next.checkoutRequested = override.checkoutRequested;
  }

  return next;
};

export const usePlanStore = create<PlanStoreState>((set, get) => {
  const initialDebugOverride = PLAN_DEBUG_TOOLS_ENABLED ? readDebugOverrideFromStorage() : null;

  const applyPlanPayloadToState = (payload: NormalizedPlanContext, extra?: Partial<PlanStoreState>) => {
    set({
      planTier: payload.planTier,
      expiresAt: payload.expiresAt,
      entitlements: payload.entitlements,
      featureFlags: payload.featureFlags,
      memoryFlags: payload.memoryFlags,
      quota: payload.quota,
      updatedAt: payload.updatedAt,
      updatedBy: payload.updatedBy,
      changeNote: payload.changeNote,
      checkoutRequested: payload.checkoutRequested,
      trial: payload.trial ?? mergeTrial(DEFAULT_PLAN_PAYLOAD.trial),
      ...extra,
    });
  };

  const initialEffectivePlan = applyDebugOverrideToPayload(DEFAULT_NORMALIZED_PLAN, initialDebugOverride);

  return {
    planTier: initialEffectivePlan.planTier,
    expiresAt: initialEffectivePlan.expiresAt,
    entitlements: initialEffectivePlan.entitlements,
    featureFlags: initialEffectivePlan.featureFlags,
    memoryFlags: initialEffectivePlan.memoryFlags,
    quota: initialEffectivePlan.quota,
    updatedAt: initialEffectivePlan.updatedAt,
    updatedBy: initialEffectivePlan.updatedBy,
    changeNote: initialEffectivePlan.changeNote,
    checkoutRequested: initialEffectivePlan.checkoutRequested,
    initialized: false,
    loading: false,
    saving: false,
    error: undefined,
    saveError: undefined,
    trial: initialEffectivePlan.trial,
    trialStarting: false,
    trialError: undefined,
    presets: null,
    presetsLoading: false,
    presetsError: undefined,
    lastServerPlan: DEFAULT_NORMALIZED_PLAN,
    debugToolsEnabled: PLAN_DEBUG_TOOLS_ENABLED,
    debugOverride: initialDebugOverride,
    async fetchPlan(options) {
      if (get().loading) {
        return;
      }
      set({ loading: true, error: undefined });

      try {
        const baseUrl = resolveApiBase();
        const response = await fetchWithAuth(`${baseUrl}/api/v1/plan/context`, {
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
        const effective = applyDebugOverrideToPayload(mapped, get().debugOverride);
        applyPlanPayloadToState(effective, {
          initialized: true,
          loading: false,
          saving: false,
          error: undefined,
          saveError: undefined,
          trialStarting: false,
          trialError: undefined,
          lastServerPlan: mapped,
        });
        if (!get().presets && !get().presetsLoading) {
          void get()
            .fetchPlanPresets(options)
            .catch(() => undefined);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'plan context fetch failed';
        logEvent('plan.context.fetch_failed', { message });

        const fallback = applyDebugOverrideToPayload(DEFAULT_NORMALIZED_PLAN, get().debugOverride);
        applyPlanPayloadToState(fallback, {
          initialized: true,
          loading: false,
          saving: false,
          error: message,
          saveError: message,
          trialStarting: false,
          trialError: message,
        });
      }
    },

    setPlanFromServer(payload) {
      logEvent('plan.context.hydrated', { planTier: payload.planTier });
      const mapped = mapPayload(payload);
      const effective = applyDebugOverrideToPayload(mapped, get().debugOverride);
      applyPlanPayloadToState(effective, {
        initialized: true,
        loading: false,
        saving: false,
        error: undefined,
        saveError: undefined,
        trialStarting: false,
        trialError: undefined,
        lastServerPlan: mapped,
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
        const response = await fetchWithAuth(`${baseUrl}/api/v1/plan/context`, {
          method: 'PATCH',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
        });

        if (!response.ok) {
          throw new Error(`failed to update plan context (${response.status})`);
        }

        const payload = (await response.json()) as PlanContextPayload;
        const mapped = mapPayload(payload);
        const effective = applyDebugOverrideToPayload(mapped, get().debugOverride);
        applyPlanPayloadToState(effective, {
          saving: false,
          saveError: undefined,
          lastServerPlan: mapped,
        });

        return payload;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'plan context update failed';
        set({ saving: false, saveError: message });
        throw error instanceof Error ? error : new Error(String(error));
      }
    },

    async startTrial(input) {
      if (get().trialStarting) {
        throw new Error('plan trial request already in flight');
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
        const response = await fetchWithAuth(`${baseUrl}/api/v1/plan/trial`, {
          method: 'POST',
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
        const effective = applyDebugOverrideToPayload(mapped, get().debugOverride);
        logEvent('plan.trial.started', {
          planTier: mapped.planTier,
          trialTier: mapped.trial.tier,
          trialActive: mapped.trial.active,
        });

        applyPlanPayloadToState(effective, {
          initialized: true,
          loading: false,
          saving: false,
          error: undefined,
          saveError: undefined,
          trialStarting: false,
          trialError: undefined,
          lastServerPlan: mapped,
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
        const response = await fetchWithAuth(`${baseUrl}/api/v1/plan/presets`, {
          cache: 'no-store',
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

    applyDebugOverride(override) {
      if (!PLAN_DEBUG_TOOLS_ENABLED) {
        return;
      }
      const normalized: PlanDebugOverride = { ...override, enabled: true };
      persistDebugOverrideToStorage(normalized);
      const base = get().lastServerPlan ?? DEFAULT_NORMALIZED_PLAN;
      const effective = applyDebugOverrideToPayload(base, normalized);
      applyPlanPayloadToState(effective, { debugOverride: normalized });
      logEvent('plan.debug.override_applied', {
        planTier: normalized.planTier ?? base.planTier,
      });
    },

    clearDebugOverride() {
      if (!PLAN_DEBUG_TOOLS_ENABLED) {
        return;
      }
      persistDebugOverrideToStorage(null);
      const base = get().lastServerPlan ?? DEFAULT_NORMALIZED_PLAN;
      applyPlanPayloadToState(base, { debugOverride: null });
      logEvent('plan.debug.override_cleared', {});
    },
  };
});
export const usePlanTier = () => usePlanStore((state) => state.planTier);
export const usePlanTrial = () => usePlanStore((state) => state.trial);
export const usePlanTrialRequestState = () =>
  usePlanStore((state) => ({
    trialStarting: state.trialStarting,
    trialError: state.trialError,
  }));
export { planTierRank, isTierAtLeast, nextTier } from '@/store/planStore/helpers';
export type {
  PlanTier,
  PlanFeatureFlags,
  PlanMemoryFlags,
  PlanQuota,
  PlanTrialState,
  PlanTrialStartInput,
  PlanPreset,
  PlanContextPayload,
  PlanContextUpdateInput,
  PlanDebugOverride,
} from '@/store/planStore/types';
