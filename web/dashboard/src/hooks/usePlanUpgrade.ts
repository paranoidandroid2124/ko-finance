"use client";

import { useCallback } from "react";
import { usePlanTier, nextTier, type PlanTier } from "@/store/planStore";
import { useTossCheckout } from "@/hooks/useTossCheckout";
import { logEvent } from "@/lib/telemetry";

type UpgradeOptions = {
  redirectPath?: string;
};

export const usePlanUpgrade = () => {
  const currentTier = usePlanTier();
  const { isPreparing, lastError, startCheckout, getPreset, getTierLabel } = useTossCheckout();

  const requestUpgrade = useCallback(
    async (requiredTier: PlanTier, options?: UpgradeOptions) => {
      if (requiredTier === "free") {
        return;
      }

      const preset = getPreset(requiredTier);
      if (!preset) {
        throw new Error("해당 플랜의 결제 정보가 아직 준비되지 않았어요.");
      }

      logEvent("payments.upgrade.cta", {
        fromTier: currentTier,
        toTier: requiredTier,
      });

      await startCheckout({
        targetTier: requiredTier,
        amount: preset.amount,
        orderName: preset.orderName,
        redirectPath: options?.redirectPath,
      });
    },
    [currentTier, getPreset, startCheckout],
  );

  const requestNextUpgrade = useCallback(
    async (options?: UpgradeOptions) => {
      const tier = nextTier(currentTier);
      if (!tier) {
        return;
      }
      await requestUpgrade(tier, options);
    },
    [currentTier, requestUpgrade],
  );

  return {
    requestUpgrade,
    requestNextUpgrade,
    isPreparing,
    lastError,
    currentTier,
    getTierLabel,
  };
};
