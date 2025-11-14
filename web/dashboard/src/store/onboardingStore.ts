"use client";

import { create } from "zustand";
import { fetchWithAuth } from "@/lib/fetchWithAuth";

export type OnboardingChecklistItem = {
  id: string;
  title: string;
  description: string;
  tips: string[];
  cta?: { label: string; href: string } | null;
};

export type OnboardingSampleSection = {
  id: string;
  title: string;
  items: Array<Record<string, unknown>>;
};

export type OnboardingContent = {
  hero: { title: string; subtitle: string; highlights: string[] };
  checklist: OnboardingChecklistItem[];
  sampleBoard: { title: string; sections: OnboardingSampleSection[] };
};

type OnboardingStore = {
  needsOnboarding: boolean;
  dismissed: boolean;
  loading: boolean;
  error: string | null;
  content: OnboardingContent | null;
  fetchContent: () => Promise<void>;
  completeOnboarding: (steps: string[]) => Promise<void>;
  markDismissed: () => void;
  setNeedsOnboarding: (value: boolean) => void;
};

export const useOnboardingStore = create<OnboardingStore>((set, get) => ({
  needsOnboarding: false,
  dismissed: false,
  loading: false,
  error: null,
  content: null,
  async fetchContent() {
    if (get().loading || get().content) {
      return;
    }
    set({ loading: true, error: null });
    try {
      const response = await fetchWithAuth("/api/v1/onboarding/content", { skipAutoSignIn: true });
      if (!response.ok) {
        throw new Error(`failed to load onboarding content (${response.status})`);
      }
      const payload = (await response.json()) as { onboardingRequired: boolean } & OnboardingContent;
      set({
        content: {
          hero: payload.hero,
          checklist: payload.checklist,
          sampleBoard: payload.sampleBoard,
        },
        needsOnboarding: payload.onboardingRequired,
        loading: false,
        error: null,
        dismissed: false,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "onboarding content fetch failed";
      set({ loading: false, error: message });
      throw error instanceof Error ? error : new Error(String(error));
    }
  },
  async completeOnboarding(steps) {
    set({ loading: true, error: null });
    try {
      const response = await fetchWithAuth("/api/v1/onboarding/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ completedSteps: steps }),
      });
      if (!response.ok) {
        throw new Error(`failed to complete onboarding (${response.status})`);
      }
      set({ needsOnboarding: false, loading: false, dismissed: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : "onboarding completion failed";
      set({ loading: false, error: message });
      throw error instanceof Error ? error : new Error(String(error));
    }
  },
  markDismissed() {
    set({ dismissed: true });
  },
  setNeedsOnboarding(value) {
    set((state) => ({
      needsOnboarding: value,
      dismissed: value ? state.dismissed : false,
    }));
  },
}));
