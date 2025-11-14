"use client";

import { useCallback } from "react";

import { usePlanStore } from "@/store/planStore";
import { useToastStore } from "@/store/toastStore";
import { logEvent } from "@/lib/telemetry";

type TrialCtaOptions = {
  source?: string;
};

export function usePlanTrialCta() {
  const pushToast = useToastStore((state) => state.show);
  const { trial, trialStarting, startTrial } = usePlanStore((state) => ({
    trial: state.trial,
    trialStarting: state.trialStarting,
    startTrial: state.startTrial,
  }));

  const trialDurationDays = trial?.durationDays ?? 7;
  const trialActive = Boolean(trial?.active);
  const trialAvailable = Boolean(trial && !trial.active && !trial.used);

  const startTrialCta = useCallback(
    async (options?: TrialCtaOptions) => {
      try {
        logEvent("plan.trial.cta_click", {
          source: options?.source ?? "unknown",
        });
        await startTrial();
        pushToast({
          id: "plan-trial-started",
          title: "Pro 플랜 체험을 시작했어요!",
          message: `${trialDurationDays}일 동안 이메일·웹훅 채널을 포함한 모든 플랜 기능을 결제 없이 바로 사용할 수 있어요.`,
          intent: "success",
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "무료 체험을 시작하지 못했어요.";
        pushToast({
          id: "plan-trial-failed",
          title: "체험을 시작할 수 없어요",
          message,
          intent: "error",
        });
        throw error instanceof Error ? error : new Error(String(error));
      }
    },
    [pushToast, startTrial, trialDurationDays],
  );

  return {
    trial,
    trialActive,
    trialAvailable,
    trialDurationDays,
    trialStarting,
    startTrialCta,
  };
}
