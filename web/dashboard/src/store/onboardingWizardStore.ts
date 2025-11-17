"use client";

import { create } from "zustand";
import type { PlanTier } from "@/store/planStore";
import {
  checkSlugAvailability,
  fetchOnboardingState,
  inviteOnboardingMembers,
  selectOnboardingPlan,
  updateOnboardingOrg,
  type OnboardingMember,
  type OnboardingOrg,
  type OnboardingState,
} from "@/lib/onboardingApi";

type OnboardingWizardStore = {
  state: OnboardingState | null;
  loading: boolean;
  error: string | null;
  fetchState: () => Promise<OnboardingState>;
  updateOrg: (payload: { name: string; slug?: string | null }) => Promise<OnboardingOrg>;
  inviteMembers: (payload: { orgId: string; invites: Array<{ email: string; role?: string }> }) => Promise<OnboardingMember[]>;
  selectPlan: (payload: { orgId: string; planTier: PlanTier }) => Promise<OnboardingOrg>;
  checkSlug: (slug: string) => Promise<boolean>;
};

export const useOnboardingWizardStore = create<OnboardingWizardStore>((set, get) => ({
  state: null,
  loading: false,
  error: null,
  async fetchState() {
    if (get().loading) {
      return get().state as OnboardingState;
    }
    set({ loading: true, error: null });
    try {
      const state = await fetchOnboardingState();
      set({ state, loading: false, error: null });
      return state;
    } catch (error) {
      const message = error instanceof Error ? error.message : "온보딩 상태 조회에 실패했습니다.";
      set({ loading: false, error: message });
      throw error instanceof Error ? error : new Error(String(error));
    }
  },
  async updateOrg(payload) {
    const org = await updateOnboardingOrg(payload);
    set((state) => ({
      state: state.state
        ? {
            ...state.state,
            org,
          }
        : state.state,
    }));
    return org;
  },
  async inviteMembers({ orgId, invites }) {
    const normalized = invites
      .map((invite) => ({
        email: invite.email.trim(),
        role: invite.role,
      }))
      .filter((invite) => invite.email.length > 0);
    if (normalized.length === 0) {
      return get().state?.members ?? [];
    }
    const members = await inviteOnboardingMembers({
      orgId,
      invites: normalized,
    });
    set((state) => ({
      state: state.state
        ? {
            ...state.state,
            members,
          }
        : state.state,
    }));
    return members;
  },
  async selectPlan(payload) {
    const org = await selectOnboardingPlan(payload);
    set((state) => ({
      state: state.state
        ? {
            ...state.state,
            org,
          }
        : state.state,
    }));
    return org;
  },
  async checkSlug(slug) {
    if (!slug.trim()) {
      return false;
    }
    return checkSlugAvailability(slug);
  },
}));
