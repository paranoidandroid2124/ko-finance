"use client";

import { useEffect } from "react";

import { usePlanStore, type PlanPreset, type PlanTier } from "@/store/planStore";

type UsePlanPresetsResult = {
  presets: Record<PlanTier, PlanPreset> | null;
  loading: boolean;
  error: string | null;
};

export function usePlanPresets(): UsePlanPresetsResult {
  const { presets, presetsLoading, presetsError, fetchPlanPresets } = usePlanStore((state) => ({
    presets: state.presets,
    presetsLoading: state.presetsLoading,
    presetsError: state.presetsError ?? null,
    fetchPlanPresets: state.fetchPlanPresets,
  }));

  useEffect(() => {
    if (!presets && !presetsLoading) {
      fetchPlanPresets().catch(() => undefined);
    }
  }, [fetchPlanPresets, presets, presetsLoading]);

  return {
    presets,
    loading: presetsLoading,
    error: presetsError ?? null,
  };
}
