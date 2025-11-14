"use client";

import { useEffect, useState } from "react";

import { usePlanTier, usePlanTrial } from "@/store/planStore";
import { usePlanUpgrade } from "@/hooks/usePlanUpgrade";
import { FEATURE_STARTER_ENABLED } from "@/config/features";
import { useCampaignSettings } from "@/hooks/useCampaignSettings";
import { recordKpiEvent } from "@/lib/kpi";

const STORAGE_KEY = "__starter_banner_dismissed__";
const FALLBACK_COPY = {
  headline: "Starter 30일 체험으로 워치리스트 자동화를 시작해 보세요",
  body: "워치리스트 50개 · 알림 룰 10개 · 하루 80회 RAG 질문이 포함됩니다. 기간 안에 해지해도 비용이 청구되지 않아요.",
  ctaLabel: "Starter 바로 시작",
  dismissLabel: "지금은 괜찮아요",
};

export function StarterPromoBanner() {
  const planTier = usePlanTier();
  const trial = usePlanTrial();
  const { requestUpgrade, isPreparing } = usePlanUpgrade();
  const { data: campaignSettings } = useCampaignSettings();
  const starterCampaign = campaignSettings?.starter_promo;
  const [dismissed, setDismissed] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  });

  const featureEnabled = FEATURE_STARTER_ENABLED;
  const campaignEnabled = featureEnabled && (starterCampaign?.enabled ?? true);
  const copy = starterCampaign?.banner ?? FALLBACK_COPY;

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    setDismissed(window.localStorage.getItem(STORAGE_KEY) === "1");
  }, []);

  useEffect(() => {
    if (!campaignEnabled || dismissed || planTier !== "free" || trial?.active) {
      return;
    }
    void recordKpiEvent("campaign.starter.banner_view", { planTier }).catch(() => undefined);
  }, [campaignEnabled, dismissed, planTier, trial?.active]);

  if (!campaignEnabled || planTier !== "free" || dismissed || trial?.active) {
    return null;
  }

  const handleDismiss = () => {
    setDismissed(true);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, "1");
    }
    void recordKpiEvent("campaign.starter.banner_dismissed", { planTier }).catch(() => undefined);
  };

  const handleUpgrade = async () => {
    void recordKpiEvent("campaign.starter.banner_click", { planTier }).catch(() => undefined);
    try {
      const redirectPath =
        typeof window !== "undefined" ? `${window.location.pathname}${window.location.search}` : "/settings";
      await requestUpgrade("starter", { redirectPath });
    } catch (error) {
      // errors surface via toast in usePlanUpgrade
    }
  };

  return (
    <div className="mb-4 rounded-xl border border-amber-300/70 bg-amber-50/90 px-4 py-3 shadow-sm transition dark:border-amber-200/50 dark:bg-amber-500/10">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold text-amber-900 dark:text-amber-100">{copy.headline}</p>
          <p className="text-xs text-amber-800/80 dark:text-amber-100/80">{copy.body}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleUpgrade}
            disabled={isPreparing}
            className="inline-flex items-center rounded-lg bg-amber-600 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-amber-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-600 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isPreparing ? "진행 중..." : copy.ctaLabel}
          </button>
          <button
            type="button"
            onClick={handleDismiss}
            className="text-xs font-medium text-amber-800 underline-offset-2 hover:underline dark:text-amber-100"
          >
            {copy.dismissLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
