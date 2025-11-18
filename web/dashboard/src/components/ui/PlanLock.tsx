"use client";

import clsx from "classnames";
import { useEffect, useMemo, useCallback } from "react";

import { logEvent } from "@/lib/telemetry";
import { getPlanBadgeTone, getPlanIcon, getPlanIconTone, getPlanLabel } from "@/lib/planTier";
import { isTierAtLeast, nextTier, type PlanTier, usePlanTier } from "@/store/planStore";
import { usePlanTrialCta } from "@/hooks/usePlanTrialCta";
import { usePlanCatalog } from "@/hooks/usePlanCatalog";
import { resolvePlanMarketingCopy } from "@/lib/planContext";
import { PlanTierCTA } from "@/components/plan/PlanTierCTA";

type PlanLockProps = {
  requiredTier: PlanTier;
  currentTier?: PlanTier;
  title?: string;
  description?: string;
  onUpgrade?: (tier: PlanTier) => void;
  className?: string;
  children?: React.ReactNode;
  showBadge?: boolean;
};

export function PlanLock({
  requiredTier,
  currentTier,
  title,
  description,
  onUpgrade,
  className,
  children,
  showBadge = true,
}: PlanLockProps) {
  const tierFromStore = usePlanTier();
  const tier = currentTier ?? tierFromStore;
  const isUnlocked = isTierAtLeast(tier, requiredTier);
  const { catalog } = usePlanCatalog();
  const { trialAvailable, trialStarting, startTrialCta } = usePlanTrialCta();
  const trialEligible = Boolean(trialAvailable && requiredTier === "pro" && tier === "free");

  const Icon = getPlanIcon(requiredTier);
  const iconTone = getPlanIconTone(requiredTier);
  const requiredLabel = getPlanLabel(requiredTier, catalog);
  const currentLabel = getPlanLabel(tier, catalog);
  const marketingCopy = useMemo(
    () => resolvePlanMarketingCopy(requiredTier, catalog),
    [requiredTier, catalog],
  );
  const heading = title ?? `${marketingCopy.title} 플랜에서 열리는 기능이에요.`;
  const detail = description ?? marketingCopy.tagline;

  const next = useMemo(() => nextTier(tier), [tier]);

  useEffect(() => {
    if (!isUnlocked) {
      logEvent("plan.lock.view", { requiredTier, currentTier: tier });
    }
  }, [isUnlocked, requiredTier, tier]);

  const handleStartTrial = useCallback(() => {
    logEvent("plan.lock.trial_click", { requiredTier, currentTier: tier });
    startTrialCta({ source: "plan-lock" }).catch(() => undefined);
  }, [requiredTier, startTrialCta, tier]);

  if (isUnlocked) {
    return children ? <>{children}</> : null;
  }

  return (
    <div
      className={clsx(
        "rounded-xl border border-dashed border-border-light/80 bg-background-cardLight/80 p-4 text-sm text-text-secondaryLight shadow-card transition-colors dark:border-border-dark/80 dark:bg-background-cardDark/50 dark:text-text-secondaryDark",
        className,
      )}
      data-testid="plan-lock"
    >
      <div className="flex items-center gap-2 text-text-primaryLight dark:text-text-primaryDark">
        <Icon aria-hidden className={clsx("h-5 w-5", iconTone)} />
        <p className="font-semibold">{heading}</p>
        {showBadge ? (
          <span className={clsx("rounded-full px-2 py-0.5 text-[11px] uppercase", getPlanBadgeTone(requiredTier))}>
            {requiredLabel}
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-xs leading-5">{detail}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {trialEligible ? (
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-lg border border-primary/60 bg-white px-3 py-2 text-xs font-semibold text-primary shadow-sm transition-motion-fast hover:bg-primary/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-60 dark:bg-transparent dark:text-primary.dark dark:hover:bg-primary.dark/20"
            onClick={handleStartTrial}
            disabled={trialStarting}
          >
            {trialStarting ? "체험 시작 중..." : "7일 무료 체험"}
          </button>
        ) : null}
        <PlanTierCTA
          tier={requiredTier}
          action={marketingCopy.primaryAction}
          onUpgrade={onUpgrade}
          onBeforeUpgrade={() =>
            logEvent("plan.lock.upgrade_click", { requiredTier, currentTier: tier, nextTier: next ?? null })
          }
          variant="primary"
          className="text-xs"
        />
      </div>
      {children ? <div className="mt-3">{children}</div> : null}
      <p className="mt-3 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
        지금은{" "}
        <strong className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">{currentLabel}</strong> 플랜을 이용 중이에요.{" "}
        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{requiredLabel}</span>로 한 단계 올라가면 바라던 기능을 바로 사용하실 수 있어요.
      </p>
    </div>
  );
}
